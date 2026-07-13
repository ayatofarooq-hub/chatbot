using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;

namespace LegalChatbotDesktop;

public sealed class BackendProcessManager : IAsyncDisposable
{
    private readonly BackendOptions _options;
    private readonly HttpClient _httpClient;
    private readonly StringBuilder _stderrBuffer = new();
    private readonly SemaphoreSlim _gate = new(1, 1);
    private Process? _process;
    private StreamWriter? _stdoutLog;
    private StreamWriter? _stderrLog;

    public BackendProcessManager(BackendOptions options, HttpClient? httpClient = null)
    {
        _options = options;
        _httpClient = httpClient ?? new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(2)
        };
    }

    public string CapturedStderr
    {
        get
        {
            lock (_stderrBuffer)
            {
                return _stderrBuffer.ToString();
            }
        }
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            if (_process is { HasExited: false })
            {
                return;
            }

            if (await IsPortInUseAsync(cancellationToken))
            {
                if (await IsHealthyAsync(cancellationToken))
                {
                    return;
                }

                throw new BackendPortInUseException(
                    $"Port {_options.Port} on {_options.Host} is already in use, but {_options.HealthUri} did not respond successfully. Close the process using the port or change the configured port.");
            }

            if (!File.Exists(_options.PythonExecutablePath))
            {
                throw new FileNotFoundException("Configured Python executable was not found.", _options.PythonExecutablePath);
            }

            if (!Directory.Exists(_options.BackendWorkingDirectory))
            {
                throw new DirectoryNotFoundException($"Configured backend working directory was not found: {_options.BackendWorkingDirectory}");
            }

            Directory.CreateDirectory(_options.ResolveLogDirectory());
            var timestamp = DateTime.Now.ToString("yyyyMMdd-HHmmss");
            _stdoutLog = new StreamWriter(Path.Combine(_options.ResolveLogDirectory(), $"backend-{timestamp}.stdout.log"), append: false, Encoding.UTF8)
            {
                AutoFlush = true
            };
            _stderrLog = new StreamWriter(Path.Combine(_options.ResolveLogDirectory(), $"backend-{timestamp}.stderr.log"), append: false, Encoding.UTF8)
            {
                AutoFlush = true
            };

            var startInfo = new ProcessStartInfo
            {
                FileName = _options.PythonExecutablePath,
                WorkingDirectory = _options.BackendWorkingDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            foreach (var argument in _options.Arguments)
            {
                startInfo.ArgumentList.Add(argument);
            }

            _process = new Process
            {
                StartInfo = startInfo,
                EnableRaisingEvents = true
            };

            _process.OutputDataReceived += (_, args) =>
            {
                if (args.Data is not null)
                {
                    _stdoutLog?.WriteLine(args.Data);
                }
            };

            _process.ErrorDataReceived += (_, args) =>
            {
                if (args.Data is not null)
                {
                    _stderrLog?.WriteLine(args.Data);
                    lock (_stderrBuffer)
                    {
                        _stderrBuffer.AppendLine(args.Data);
                    }
                }
            };

            if (!_process.Start())
            {
                throw new InvalidOperationException("Failed to start the backend process.");
            }

            _process.BeginOutputReadLine();
            _process.BeginErrorReadLine();
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task WaitForHealthyAsync(IProgress<string>? progress = null, CancellationToken cancellationToken = default)
    {
        var timeout = TimeSpan.FromSeconds(Math.Max(1, _options.StartupTimeoutSeconds));
        var pollInterval = TimeSpan.FromMilliseconds(Math.Max(100, _options.PollIntervalMilliseconds));
        var deadline = DateTimeOffset.UtcNow + timeout;

        while (DateTimeOffset.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (_process?.HasExited == true)
            {
                throw new BackendStartupException(
                    $"Backend process exited with code {_process.ExitCode} before becoming healthy.",
                    CapturedStderr);
            }

            if (await IsHealthyAsync(cancellationToken))
            {
                return;
            }

            progress?.Report($"Waiting for backend at {_options.HealthUri}...");
            await Task.Delay(pollInterval, cancellationToken);
        }

        throw new BackendStartupException(
            $"Backend did not respond at {_options.HealthUri} within {_options.StartupTimeoutSeconds} seconds.",
            CapturedStderr);
    }

    public async Task<bool> IsHealthyAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            using var response = await _httpClient.GetAsync(_options.HealthUri, cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException)
        {
            return false;
        }
        catch (TaskCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return false;
        }
    }

    public async Task StopAsync()
    {
        await _gate.WaitAsync();
        try
        {
            if (_process is null)
            {
                return;
            }

            try
            {
                if (!_process.HasExited)
                {
                    _process.CloseMainWindow();

                    if (!await WaitForExitAsync(_process, TimeSpan.FromSeconds(5)))
                    {
                        _process.Kill(entireProcessTree: true);
                        await WaitForExitAsync(_process, TimeSpan.FromSeconds(5));
                    }
                }
            }
            finally
            {
                _process.Dispose();
                _process = null;
                await DisposeLogsAsync();
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync();
        _httpClient.Dispose();
        _gate.Dispose();
    }

    private async Task<bool> IsPortInUseAsync(CancellationToken cancellationToken)
    {
        using var tcpClient = new TcpClient();
        try
        {
            await tcpClient.ConnectAsync(_options.Host, _options.Port, cancellationToken);
            return true;
        }
        catch (SocketException)
        {
            return false;
        }
    }

    private static async Task<bool> WaitForExitAsync(Process process, TimeSpan timeout)
    {
        using var cts = new CancellationTokenSource(timeout);
        try
        {
            await process.WaitForExitAsync(cts.Token);
            return true;
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }

    private async Task DisposeLogsAsync()
    {
        if (_stdoutLog is not null)
        {
            await _stdoutLog.DisposeAsync();
            _stdoutLog = null;
        }

        if (_stderrLog is not null)
        {
            await _stderrLog.DisposeAsync();
            _stderrLog = null;
        }
    }
}

public sealed class BackendPortInUseException : Exception
{
    public BackendPortInUseException(string message) : base(message)
    {
    }
}

public sealed class BackendStartupException : Exception
{
    public BackendStartupException(string message, string stderr) : base(message)
    {
        Stderr = stderr;
    }

    public string Stderr { get; }
}
