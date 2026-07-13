using Microsoft.Web.WebView2.Core;
using System.IO;
using System.Windows;

namespace LegalChatbotDesktop;

public partial class MainWindow : Window
{
    private readonly BackendOptions _options;
    private readonly BackendProcessManager _backend;
    private CancellationTokenSource? _startupCancellation;
    private bool _isClosing;

    public MainWindow()
    {
        InitializeComponent();
        _options = BackendOptions.Load();
        _backend = new BackendProcessManager(_options);
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        await StartBackendAndNavigateAsync();
    }

    private async void RetryButton_Click(object sender, RoutedEventArgs e)
    {
        await StartBackendAndNavigateAsync();
    }

    private async Task StartBackendAndNavigateAsync()
    {
        _startupCancellation?.Cancel();
        _startupCancellation?.Dispose();
        _startupCancellation = new CancellationTokenSource();

        ShowLoading("Launching backend process");

        try
        {
            await _backend.StartAsync(_startupCancellation.Token);

            var progress = new Progress<string>(message => StatusText.Text = message);
            await _backend.WaitForHealthyAsync(progress, _startupCancellation.Token);

            StatusText.Text = "Opening desktop shell";
            var webViewDataFolder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "LegalChatbotDesktop",
                "WebView2");
            Directory.CreateDirectory(webViewDataFolder);
            var webViewEnvironment = await CoreWebView2Environment.CreateAsync(userDataFolder: webViewDataFolder);
            await BrowserView.EnsureCoreWebView2Async(webViewEnvironment);
            BrowserView.Source = new Uri(_options.FrontendUrl);

            SplashView.Visibility = Visibility.Collapsed;
            BrowserView.Visibility = Visibility.Visible;
        }
        catch (OperationCanceledException) when (_isClosing)
        {
        }
        catch (BackendPortInUseException ex)
        {
            ShowError(ex.Message, "Port 8000 is already occupied. Stop the existing process or update appsettings.json to use a different port.");
        }
        catch (BackendStartupException ex)
        {
            ShowError(ex.Message, string.IsNullOrWhiteSpace(ex.Stderr) ? "No stderr output was captured." : ex.Stderr);
        }
        catch (Exception ex)
        {
            ShowError("Backend startup failed.", ex.ToString());
        }
    }

    private void ShowLoading(string message)
    {
        SplashView.Visibility = Visibility.Visible;
        BrowserView.Visibility = Visibility.Collapsed;
        StartupProgress.IsIndeterminate = true;
        StartupProgress.Visibility = Visibility.Visible;
        RetryButton.Visibility = Visibility.Collapsed;
        ErrorDetails.Visibility = Visibility.Collapsed;
        ErrorDetails.Text = string.Empty;
        StatusText.Text = message;
    }

    private void ShowError(string message, string details)
    {
        SplashView.Visibility = Visibility.Visible;
        BrowserView.Visibility = Visibility.Collapsed;
        StartupProgress.IsIndeterminate = false;
        StartupProgress.Visibility = Visibility.Collapsed;
        RetryButton.Visibility = Visibility.Visible;
        ErrorDetails.Visibility = Visibility.Visible;
        StatusText.Text = message;
        ErrorDetails.Text = details;
    }

    private async void Window_Closing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        if (_isClosing)
        {
            return;
        }

        _isClosing = true;
        e.Cancel = true;

        _startupCancellation?.Cancel();
        BrowserView.Dispose();
        await _backend.StopAsync();

        e.Cancel = false;
        Close();
    }
}
