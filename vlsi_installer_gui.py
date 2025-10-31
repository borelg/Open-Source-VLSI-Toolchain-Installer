
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
import shutil
import datetime

# Define a directory to clone the source code into
SRC_DIR = os.path.expanduser("~/vlsi_tools_src")

# --- Tool Definitions ---
# Each tool is a dictionary containing:
# - name: Display name for the GUI
# - check: A shell command to check if the tool is installed.
#          It should return exit code 0 if installed, non-zero otherwise.
# - commands: A list of shell commands to run for installation.
#             'cd' is handled by setting the 'cwd' for each command.
# - repo_dir: The name of the directory created by git clone.

TOOLS = [
    {
        "name": "Required Packages",
        "check": "dpkg -s git >/dev/null 2>&1", # Just check for git, apt will handle the rest
        "repo_dir": None,
        "commands": [
            ("sudo apt-get update", None),
            ("sudo apt-get install -y git vim m4 tcsh csh libx11-dev tcl-dev tk-dev libcairo2-dev mesa-common-dev libglu1-mesa-dev libncurses-dev flex bison libxpm-dev libxaw7-dev libreadline-dev libgtk-3-dev xterm", None),
        ],
    },
    {
        "name": "Magic",
        "check": "which magic",
        "repo_dir": "magic",
        "commands": [
            ("git clone https://github.com/RTimothyEdwards/magic", SRC_DIR),
            ("unset CAD_ROOT && ./configure --prefix=/usr/local --enable-cairo-offscreen", "magic"),
            ("unset CAD_ROOT && make", "magic"),
            ("sudo make install", "magic"),
        ],
    },
    {
        "name": "Xschem",
        "check": "which xschem",
        "repo_dir": "xschem",
        "commands": [
            ("git clone https://github.com/StefanSchippers/xschem", SRC_DIR),
            ("./configure", "xschem"),
            ("make", "xschem"),
            ("sudo make install", "xschem"),
        ],
    },
    {
        "name": "Ngspice",
        "check": "which ngspice",
        "repo_dir": "ngspice",
        "commands": [
            ("sudo apt-get install -y libfftw3-dev autoconf automake libtool", None),
            ("git clone git://git.code.sf.net/p/ngspice/ngspice", SRC_DIR),
            ("./autogen.sh", "ngspice"),
            ("./configure --with-x --enable-xspice --disable-debug --enable-cider --with-readlines=yes --enable-predictor --enable-osdi --enable-openmp", "ngspice"),
            ("make -j$(nproc)", "ngspice"),
            ("sudo make install", "ngspice"),
        ],
    },
    {
        "name": "GAW",
        "check": "which gaw",
        "repo_dir": "xschem-gaw",
        "commands": [
            ("sudo apt-get install -y libgtk-3-dev xterm", None),
            ("git clone https://github.com/StefanSchippers/xschem-gaw", SRC_DIR),
            ("./configure", "xschem-gaw"),
            ("make", "xschem-gaw"),
            ("sudo make install", "xschem-gaw"),
        ],
    },
    {
        "name": "Netgen",
        "check": "which netgen",
        "repo_dir": "netgen",
        "commands": [
            ("git clone https://github.com/RTimothyEdwards/netgen", SRC_DIR),
            ("./configure", "netgen"),
            ("make", "netgen"),
            ("sudo make install", "netgen"),
        ],
    },
    {
        "name": "Open PDKs",
        "check": "test -d /usr/local/share/pdk/sky130A",
        "repo_dir": "open_pdks",
        "commands": [
            ("git clone https://github.com/RTimothyEdwards/open_pdks", SRC_DIR),
            ("./configure --enable-sky130-pdk --enable-sram-sky130", "open_pdks"),
            ("PATH=/usr/local/bin:$PATH make -j$(nproc)", "open_pdks"),
            ("sudo PATH=/usr/local/bin:$PATH make install", "open_pdks"),
        ],
    },
]


class VLSIInstallerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Open-Source VLSI Tool Installer")
        self.root.geometry("800x600")

        self.tools_frame = ttk.Frame(root, padding="10")
        self.tools_frame.pack(fill=tk.X, padx=10, pady=5)

        self.log_frame = ttk.Frame(root, padding="10")
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, bg="black", fg="white", font=("monospace", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.insert(tk.END, "Welcome to the VLSI Tool Installer!\n")
        self.log_text.insert(tk.END, f"Source code will be downloaded to {SRC_DIR}\n")
        self.log_text.insert(tk.END, "Installation logs will be saved to *.log files in the script's directory.\n\n")

        self.tool_widgets = {}
        self.setup_ui()
        
        if not os.path.exists(SRC_DIR):
            os.makedirs(SRC_DIR)
            self.log_message(f"Created source directory: {SRC_DIR}")

        self.check_all_statuses()

    def setup_ui(self):
        # Create headers
        ttk.Label(self.tools_frame, text="Tool", font=("", 10, "bold")).grid(row=0, column=0, padx=5, sticky="w")
        ttk.Label(self.tools_frame, text="Status", font=("", 10, "bold")).grid(row=0, column=1, padx=5, sticky="w")
        
        for i, tool in enumerate(TOOLS):
            name = tool["name"]
            self.tool_widgets[name] = {}

            label = ttk.Label(self.tools_frame, text=name)
            label.grid(row=i + 1, column=0, sticky="w", padx=5, pady=2)

            status_label = ttk.Label(self.tools_frame, text="⚪ Checking...", foreground="gray")
            status_label.grid(row=i + 1, column=1, sticky="w", padx=5)

            install_button = ttk.Button(self.tools_frame, text="Install", command=lambda t=tool: self.start_installation(t))
            install_button.grid(row=i + 1, column=2, sticky="e", padx=5)

            self.tool_widgets[name]["label"] = label
            self.tool_widgets[name]["status"] = status_label
            self.tool_widgets[name]["button"] = install_button

    def log_message(self, message):
        self.root.after(0, self._insert_log, message)

    def _insert_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def update_status(self, tool_name, text, color):
        def _update():
            self.tool_widgets[tool_name]["status"].config(text=text, foreground=color)
        self.root.after(0, _update)

    def set_button_state(self, tool_name, state):
        self.root.after(0, lambda: self.tool_widgets[tool_name]["button"].config(state=state))

    def check_all_statuses(self):
        for tool in TOOLS:
            thread = threading.Thread(target=self.check_status, args=(tool,), daemon=True)
            thread.start()

    def check_status(self, tool):
        tool_name = tool["name"]
        try:
            # Use shell=True for simplicity with commands like 'which' and 'test'
            result = subprocess.run(tool["check"], shell=True, check=True, capture_output=True)
            if result.returncode == 0:
                self.update_status(tool_name, "🟢 Installed", "green")
                self.set_button_state(tool_name, tk.DISABLED)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.update_status(tool_name, "🔴 Not Installed", "red")
            self.set_button_state(tool_name, tk.NORMAL)

    def start_installation(self, tool):
        self.set_button_state(tool["name"], tk.DISABLED)
        self.update_status(tool["name"], "🟡 Installing...", "orange")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{tool['name'].lower().replace(' ', '_')}_{timestamp}.log"
        
        with open(log_filename, 'w') as f:
            f.write(f"--- Log for {tool['name']} - {timestamp} ---\n")

        install_thread = threading.Thread(target=self.run_installation, args=(tool, log_filename), daemon=True)
        install_thread.start()

    def run_installation(self, tool, log_filename):
        tool_name = tool["name"]
        self.log_message(f"--- Starting installation for {tool_name} (logging to {log_filename}) ---")

        with open(log_filename, 'a') as log_file:
            for cmd, cwd_suffix in tool["commands"]:
                # Determine the correct working directory
                if cwd_suffix:
                    # If it's a repo dir, it's inside SRC_DIR
                    cwd = os.path.join(SRC_DIR, cwd_suffix)
                else:
                    # If None, use the base SRC_DIR or the script's dir
                    cwd = SRC_DIR

                log_line = f"Running command: '{cmd}' in '{cwd}'"
                self.log_message(log_line)
                log_file.write(log_line + '\n')
                
                try:
                    process = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

                    for line in iter(process.stdout.readline, ''):
                        stripped_line = line.strip()
                        self.log_message(stripped_line)
                        log_file.write(stripped_line + '\n')
                        log_file.flush()

                    process.wait()

                    if process.returncode != 0:
                        error_line = f"!!! ERROR: Command failed with exit code {process.returncode} !!!"
                        self.log_message(error_line)
                        log_file.write(error_line + '\n')
                        self.update_status(tool_name, "🟠 Failed", "orange")
                        self.set_button_state(tool_name, tk.NORMAL) 
                        return

                except Exception as e:
                    error_line = f"!!! EXCEPTION: An error occurred: {e} !!!"
                    self.log_message(error_line)
                    log_file.write(error_line + '\n')
                    self.update_status(tool_name, "🟠 Failed", "orange")
                    self.set_button_state(tool_name, tk.NORMAL)
                    return
        
        success_line = f"--- Successfully completed installation for {tool_name} ---"
        self.log_message(success_line)
        with open(log_filename, 'a') as log_file:
            log_file.write(success_line + '\n')

        self.check_status(tool) # Re-check to confirm and update status to green


if __name__ == "__main__":
    root = tk.Tk()
    app = VLSIInstallerApp(root)
    root.mainloop()
