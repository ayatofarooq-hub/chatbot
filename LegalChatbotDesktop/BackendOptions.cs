using System.IO;
using System.Text.Json;

namespace LegalChatbotDesktop;

public sealed class BackendOptions
{
    public string PythonExecutablePath { get; init; } = @"C:\Path\To\Your\PythonProject\.venv\Scripts\python.exe";
    public string BackendWorkingDirectory { get; init; } = @"C:\Path\To\Your\PythonProject";
    public string[] Arguments { get; init; } =
    [
        "-m",
        "uvicorn",
        "app.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000"
    ];
    public string Host { get; init; } = "127.0.0.1";
    public int Port { get; init; } = 8000;
    public string HealthPath { get; init; } = "/health";
    public string FrontendUrl { get; init; } = "http://127.0.0.1:8000/";
    public int StartupTimeoutSeconds { get; init; } = 30;
    public int PollIntervalMilliseconds { get; init; } = 500;
    public string LogDirectory { get; init; } = "logs";

    public Uri HealthUri => new($"http://{Host}:{Port}{HealthPath}");

    public string ResolveLogDirectory()
    {
        return Path.IsPathRooted(LogDirectory)
            ? LogDirectory
            : Path.Combine(AppContext.BaseDirectory, LogDirectory);
    }

    public static BackendOptions Load(string? path = null)
    {
        path ??= Path.Combine(AppContext.BaseDirectory, "appsettings.json");

        if (!File.Exists(path))
        {
            return new BackendOptions();
        }

        using var stream = File.OpenRead(path);
        var root = JsonSerializer.Deserialize<AppSettingsRoot>(
            stream,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

        return root?.Backend ?? new BackendOptions();
    }

    private sealed class AppSettingsRoot
    {
        public BackendOptions? Backend { get; init; }
    }
}
