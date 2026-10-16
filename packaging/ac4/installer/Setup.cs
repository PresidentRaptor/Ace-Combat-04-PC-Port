using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

[assembly: AssemblyTitle("Ace Combat 04 PC Port Setup")]
[assembly: AssemblyProduct("Ace Combat 04 PC Port")]
[assembly: AssemblyVersion("2.2.1.0")]
[assembly: AssemblyFileVersion("2.2.1.0")]

internal sealed class Setup : Form
{
    TextBox iso = new TextBox(), folder = new TextBox();
    Button chooseIso = new Button(), chooseFolder = new Button(), install = new Button(), close = new Button();
    CheckBox shortcut = new CheckBox();
    Label status = new Label(); ProgressBar progress = new ProgressBar();
    CancellationTokenSource cancellation;
    bool completed;

    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new Setup());
    }

    internal Setup()
    {
        SuspendLayout();
        Text = "Ace Combat 04 PC Port - Setup 2.2.1 Beta";
        ClientSize = new Size(660, 456);
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        AutoScaleDimensions = new SizeF(96, 96); AutoScaleMode = AutoScaleMode.Dpi;
        Font = new Font("Segoe UI", 10); BackColor = Color.FromArgb(15, 28, 46); ForeColor = Color.FromArgb(214, 234, 248);
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        Label title = LabelAt("ACE COMBAT 04: SHATTERED SKIES", 24, 22, 612, 32);
        title.Font = new Font("Segoe UI", 16, FontStyle.Bold);
        LabelAt("PC Port 2.2.1 Beta  |  Windows 10/11 x64  |  Vulkan 1.3 GPU required", 24, 62, 612, 26);
        LabelAt("Choose your unmodified USA ISO (SLUS-20152). Setup checks the game\nexecutable, copies the disc, and prepares the local game data.", 24, 98, 612, 48);
        LabelAt("Game ISO", 24, 160, 612, 24);
        iso.SetBounds(24, 188, 500, 28); Controls.Add(iso);
        chooseIso.Text = "Browse..."; chooseIso.SetBounds(536, 186, 100, 32); Style(chooseIso);
        chooseIso.Click += delegate {
            using (OpenFileDialog dialog = new OpenFileDialog { Title = "Select Ace Combat 04 USA ISO", Filter = "ISO disc image (*.iso)|*.iso", CheckFileExists = true })
                if (dialog.ShowDialog(this) == DialogResult.OK) iso.Text = dialog.FileName;
        };
        LabelAt("Game folder (must be empty)", 24, 230, 612, 24);
        folder.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Games", "Ace Combat 04 PC Port");
        folder.SetBounds(24, 258, 500, 28); Controls.Add(folder);
        chooseFolder.Text = "Browse..."; chooseFolder.SetBounds(536, 256, 100, 32); Style(chooseFolder);
        chooseFolder.Click += delegate {
            using (FolderBrowserDialog dialog = new FolderBrowserDialog { Description = "Choose an empty game folder", SelectedPath = folder.Text })
                if (dialog.ShowDialog(this) == DialogResult.OK) folder.Text = dialog.SelectedPath;
        };
        shortcut.Text = "Create a desktop shortcut"; shortcut.Checked = true;
        shortcut.SetBounds(24, 304, 500, 26); Controls.Add(shortcut);
        progress.SetBounds(24, 342, 612, 16); Controls.Add(progress);
        status.SetBounds(24, 365, 612, 24); status.Text = "Your own ISO is required. No game disc or extracted assets are bundled."; Controls.Add(status);
        install.Text = "Install"; install.SetBounds(408, 406, 108, 32); Style(install); install.Click += Install;
        close.Text = "Close"; close.SetBounds(528, 406, 108, 32); Style(close);
        close.Click += delegate { if (cancellation != null) cancellation.Cancel(); else Close(); };
        FormClosing += delegate(object sender, FormClosingEventArgs e) {
            if (cancellation != null) { cancellation.Cancel(); status.Text = "Cancelling and removing unfinished files..."; e.Cancel = true; }
        };
        ResumeLayout(false);
    }

    Label LabelAt(string text, int x, int y, int w, int h)
    {
        Label label = new Label { Text = text }; label.SetBounds(x, y, w, h); Controls.Add(label); return label;
    }
    void Style(Button button)
    {
        button.BackColor = Color.FromArgb(41, 80, 116); button.ForeColor = ForeColor;
        button.FlatStyle = FlatStyle.Flat; Controls.Add(button);
    }
    async void Install(object sender, EventArgs args)
    {
        if (completed) {
            try { Process.Start(new ProcessStartInfo(Path.Combine(folder.Text, "Ace Combat 04.exe")) { WorkingDirectory = folder.Text, UseShellExecute = true }); Close(); }
            catch (Exception ex) { MessageBox.Show(this, ex.Message, "Cannot start game", MessageBoxButtons.OK, MessageBoxIcon.Error); }
            return;
        }
        if (!File.Exists(iso.Text)) { MessageBox.Show(this, "Choose your Ace Combat 04 USA ISO first."); return; }
        string isoPath = iso.Text, destination = folder.Text;
        string link = shortcut.Checked ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Ace Combat 04 PC Port.lnk") : null;
        cancellation = new CancellationTokenSource();
        CancellationToken token = cancellation.Token;
        install.Enabled = chooseIso.Enabled = chooseFolder.Enabled = iso.Enabled = folder.Enabled = shortcut.Enabled = false;
        close.Text = "Cancel";
        // Progress<T> marshals updates to the UI thread and throttling prevents
        // the several-GB ISO copy from flooding the Windows message queue.
        int last = -1;
        IProgress<Tuple<int, string>> updates = new Progress<Tuple<int, string>>(p => { progress.Value = p.Item1; status.Text = p.Item2; });
        try {
            await Task.Run(() => {
                using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")) {
                    if (payload == null) throw new InvalidDataException("Installer payload is missing.");
                    InstallerCore.Install(isoPath, destination, link, payload, (n, text) => {
                        if (n != last) { last = n; updates.Report(Tuple.Create(n, text)); }
                    }, token);
                }
            });
            completed = true; install.Text = "Launch game";
            MessageBox.Show(this, "Installation complete.\n\n" + destination + "\n\nF4 opens settings. Keep the saves folder when updating.", "Ace Combat 04 PC Port", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
        catch (OperationCanceledException) { status.Text = "Installation cancelled. No unfinished game folder was kept."; progress.Value = 0; }
        catch (Exception ex) { status.Text = "Installation could not finish."; MessageBox.Show(this, ex.Message, "Setup", MessageBoxButtons.OK, MessageBoxIcon.Error); }
        finally {
            cancellation.Dispose(); cancellation = null; close.Text = "Close"; install.Enabled = true;
            if (!completed) chooseIso.Enabled = chooseFolder.Enabled = iso.Enabled = folder.Enabled = shortcut.Enabled = true;
        }
    }
}
