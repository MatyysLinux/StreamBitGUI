import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import subprocess
import os
import json

# Define the Baudrate globally or ensure it's accessible (already part of config)
# BAUDRATE = 115200 # This is now taken from self.config['baud_rates']

class MicrobitController:
    def __init__(self, root):
        self.root = root
        self.root.title("Microbit Serial Command Controller")
        # Set a larger default geometry for better visibility
        self.root.geometry("1000x750")

        self.serial_connections = [None, None]  # Support for max 2 microbits
        self.is_running = [False, False]
        self.read_threads = [None, None]

        # Track if second microbit is enabled
        self.second_microbit_enabled = False

        # Buffer for log messages before UI is ready
        self.log_buffer = []
        self.log_text = None

        # Configuration file path
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

        # Default configuration
        self.default_config = {
            'command_mappings': {
                'a': '',
                'b': '',
                'ab': '',
                'p0': '',
                'p1': '',
                'p2': '',
                'logo': '',
                'shake': '',
                'a2': '',
                'b2': '',
                'ab2': '',
                'p02': '',
                'p12': '',
                'p22': '',
                'logo2': '',
                'shake2': ''
            },
            'last_ports': ['', ''],
            'baud_rates': ['115200', '115200'],
            'window_geometry': '1000x750', # Updated default in config as well
            'second_microbit_enabled': False
        }

        # Load configuration
        # MODIFIED: Get a flag indicating if the config file existed
        self.config, config_existed = self.load_config()
        self.command_mappings = self.config['command_mappings']
        self.second_microbit_enabled = self.config.get('second_microbit_enabled', False)

        # MODIFIED: If config.json didn't exist, save the default config immediately
        if not config_existed:
            self.log("Config file did not exist. Creating with default settings.")
            self.save_config(show_log=False) # Save silently

        # Store command entry references
        self.command_entries = {}

        self.setup_ui()
        self.refresh_ports()
        self.load_ui_settings()

        # Display buffered log messages
        self.flush_log_buffer()

    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Control frame for add/remove microbit 2
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.toggle_microbit2_btn = ttk.Button(control_frame,
                                              text="Add Microbit 2" if not self.second_microbit_enabled else "Remove Microbit 2",
                                              command=self.toggle_second_microbit)
        self.toggle_microbit2_btn.pack(side=tk.LEFT)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Microbit 1 Tab (always present)
        self.microbit1_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.microbit1_frame, text="Microbit 1")
        self.setup_microbit_tab(self.microbit1_frame, 0)

        # Microbit 2 Tab (conditional)
        self.microbit2_frame = None
        if self.second_microbit_enabled:
            self.add_microbit2_tab()

        # Log Section
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="10")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).grid(row=1, column=0, pady=(5, 0))

        # Configure main grid weights
        main_frame.rowconfigure(0, weight=0)
        main_frame.rowconfigure(1, weight=1) # Notebook takes available vertical space
        main_frame.rowconfigure(2, weight=1) # Log section takes available vertical space

    def setup_microbit_tab(self, parent, microbit_index):
        """Setup UI for a single microbit tab"""
        parent.columnconfigure(1, weight=1) # Make the command entry column expandable

        # Serial Connection Section
        connection_frame = ttk.LabelFrame(parent, text=f"Microbit {microbit_index + 1} Connection", padding="10")
        connection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        connection_frame.columnconfigure(1, weight=1) # Port and Baudrate comboboxes expand

        # COM Port selection
        ttk.Label(connection_frame, text="COM Port:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

        port_var = tk.StringVar()
        port_combo = ttk.Combobox(connection_frame, textvariable=port_var, state="readonly")
        port_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))

        # Store references for each microbit
        if microbit_index == 0:
            self.port_var1 = port_var
            self.port_combo1 = port_combo
        else: # microbit_index == 1
            self.port_var2 = port_var
            self.port_combo2 = port_combo

        ttk.Button(connection_frame, text="Refresh",
                  command=lambda: self.refresh_ports_for_microbit(microbit_index)).grid(row=0, column=2, padx=(5, 0))

        # Baud Rate
        ttk.Label(connection_frame, text="Baud Rate:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        baud_var = tk.StringVar(value=self.config['baud_rates'][microbit_index])
        baud_combo = ttk.Combobox(connection_frame, textvariable=baud_var,
                                 values=["9600", "19200", "38400", "57600", "115200"], state="readonly")
        baud_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5, 0), padx=(0, 5))
        baud_combo.bind('<<ComboboxSelected>>', self.on_setting_changed)

        # Store baud rate variables
        if microbit_index == 0:
            self.baud_var1 = baud_var
        else: # microbit_index == 1
            self.baud_var2 = baud_var

        # Connection buttons
        button_frame = ttk.Frame(connection_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=(10, 0))

        connect_btn = ttk.Button(button_frame, text="Start Server",
                                 command=lambda: self.toggle_connection(microbit_index))
        connect_btn.pack(side=tk.LEFT, padx=(0, 5))

        status_label = ttk.Label(button_frame, text="Disconnected", foreground="red")
        status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Store button and status references correctly for both microbits
        if microbit_index == 0:
            self.connect_btn1 = connect_btn
            self.status_label1 = status_label
        else: # microbit_index == 1
            self.connect_btn2 = connect_btn
            self.status_label2 = status_label


        # Command Mapping Section for this microbit
        self.setup_command_mapping_for_microbit(parent, microbit_index)

    def setup_command_mapping_for_microbit(self, parent, microbit_index):
        """Setup command mapping section for a specific microbit"""
        mapping_frame = ttk.LabelFrame(parent, text=f"Microbit {microbit_index + 1} Command Mappings", padding="10")
        mapping_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        mapping_frame.columnconfigure(1, weight=1) # Make the entry column expandable

        # Get the appropriate command list
        if microbit_index == 0:
            commands = ['a', 'b', 'ab', 'p0', 'p1', 'p2', 'logo', 'shake']
        else:
            commands = ['a2', 'b2', 'ab2', 'p02', 'p12', 'p22', 'logo2', 'shake2']

        # Create command mapping entries
        for i, cmd in enumerate(commands):
            # Display label (remove "2" suffix for display on Microbit 2 tab)
            if microbit_index == 1:
                # Only remove the trailing '2' for Microbit 2 commands
                if cmd.endswith('2'):
                    display_cmd = cmd[:-1]  # Remove last character (the '2')
                else:
                    display_cmd = cmd
            else:
                display_cmd = cmd

            ttk.Label(mapping_frame, text=f"{display_cmd}:").grid(row=i, column=0, sticky=tk.W, padx=(0, 5), pady=2)

            entry = ttk.Entry(mapping_frame, width=50) # Increased default width for entries
            entry.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=(0, 0), pady=2)
            entry.insert(0, self.command_mappings[cmd])
            self.command_entries[cmd] = entry

            entry.bind('<KeyRelease>', lambda e, command=cmd: self.update_command_mapping(command))

        # Save button for this microbit
        save_frame = ttk.Frame(mapping_frame)
        save_frame.grid(row=len(commands), column=0, columnspan=2, pady=(10, 0))

        # Removed the "Update Microbit X Commands" button
        # ttk.Button(save_frame, text=f"Update Microbit {microbit_index + 1} Commands",
        #           command=lambda: self.update_commands_for_microbit(microbit_index)).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(save_frame, text="Save Config",
                  command=self.save_config_manual).pack(side=tk.LEFT)

        # Configure grid weight for the mapping frame
        parent.rowconfigure(1, weight=1) # Make the command mapping section expandable

    def update_commands_for_microbit(self, microbit_index):
        """Update command mappings for a specific microbit"""
        if microbit_index == 0:
            commands = ['a', 'b', 'ab', 'p0', 'p1', 'p2', 'logo', 'shake']
        else:
            commands = ['a2', 'b2', 'ab2', 'p02', 'p12', 'p22', 'logo2', 'shake2']

        for cmd in commands:
            if cmd in self.command_entries:
                self.command_mappings[cmd] = self.command_entries[cmd].get()

        self.log(f"Microbit {microbit_index + 1} command mappings updated")
        self.save_config(show_log=False)

    def toggle_second_microbit(self):
        """Toggle the second microbit on/off"""
        if self.second_microbit_enabled:
            # Remove second microbit
            if self.is_running[1]:
                self.stop_server(1)

            # Remove the tab
            if self.microbit2_frame:
                self.notebook.forget(self.microbit2_frame)
                self.microbit2_frame = None

            # Crucially, remove the attributes for microbit 2 to avoid stale references
            if hasattr(self, 'port_var2'):
                del self.port_var2
            if hasattr(self, 'port_combo2'):
                del self.port_combo2
            if hasattr(self, 'baud_var2'):
                del self.baud_var2
            if hasattr(self, 'connect_btn2'):
                del self.connect_btn2
            if hasattr(self, 'status_label2'):
                del self.status_label2


            # Remove Microbit 2 command entries from the dictionary
            commands2 = ['a2', 'b2', 'ab2', 'p02', 'p12', 'p22', 'logo2', 'shake2']
            for cmd in commands2:
                if cmd in self.command_mappings: # Only delete if it exists
                    del self.command_mappings[cmd] # Also delete from self.command_mappings
                if cmd in self.command_entries:
                    del self.command_entries[cmd]

            self.second_microbit_enabled = False
            self.toggle_microbit2_btn.config(text="Add Microbit 2")
            self.log("Microbit 2 removed")
        else:
            # Add second microbit
            self.add_microbit2_tab()
            self.second_microbit_enabled = True
            self.toggle_microbit2_btn.config(text="Remove Microbit 2")
            self.log("Microbit 2 added")

        # Save configuration
        self.config['second_microbit_enabled'] = self.second_microbit_enabled
        self.save_config(show_log=False)

    def add_microbit2_tab(self):
        """Add the Microbit 2 tab"""
        self.microbit2_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.microbit2_frame, text="Microbit 2")
        self.setup_microbit_tab(self.microbit2_frame, 1)
        self.refresh_ports_for_microbit(1)
        # Ensure command mappings for Microbit 2 are initialized if not present
        for cmd in self.default_config['command_mappings']:
            if cmd.endswith('2') and cmd not in self.command_mappings:
                self.command_mappings[cmd] = self.default_config['command_mappings'][cmd]


    def load_config(self):
        """Load configuration from JSON file.
        Returns a tuple: (config_dict, file_existed_boolean)
        """
        config_existed = False
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                config_existed = True
                # Merge with default config to ensure all keys exist
                config = self.default_config.copy()
                config.update(loaded_config)
                # Ensure command_mappings has all required keys
                for cmd in self.default_config['command_mappings']:
                    if cmd not in config['command_mappings']:
                        config['command_mappings'][cmd] = self.default_config['command_mappings'][cmd]
                # Ensure lists have correct length
                if len(config.get('last_ports', [])) < 2:
                    config['last_ports'] = ['', '']
                if len(config.get('baud_rates', [])) < 2:
                    config['baud_rates'] = ['115200', '115200']
                self.log("Configuration loaded from config.json")
                return config, config_existed
            else:
                self.log("Config file not found, using defaults")
                return self.default_config.copy(), config_existed
        except Exception as e:
            self.log(f"Error loading config: {str(e)}, using defaults")
            return self.default_config.copy(), config_existed

    def save_config(self, show_log=True):
        """Save current configuration to JSON file"""
        try:
            # Update config with current settings
            self.config['command_mappings'] = self.command_mappings.copy()
            # Safely access attributes only if they exist
            self.config['last_ports'] = [self.port_var1.get(), self.port_var2.get() if hasattr(self, 'port_var2') else '']
            self.config['baud_rates'] = [self.baud_var1.get(), self.baud_var2.get() if hasattr(self, 'baud_var2') else '115200']
            self.config['window_geometry'] = self.root.geometry()
            self.config['second_microbit_enabled'] = self.second_microbit_enabled

            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)

            if show_log:
                self.log("Configuration saved to config.json")
        except Exception as e:
            if show_log:
                self.log(f"Error saving config: {str(e)}")
                messagebox.showerror("Save Error", f"Failed to save configuration: {str(e)}")

    def save_config_manual(self):
        """Manually save configuration (called by Save Config button)"""
        self.update_all_commands()
        self.save_config()
        messagebox.showinfo("Saved", "Configuration saved successfully!")

    def update_all_commands(self):
        """Update all command mappings from the entry fields"""
        for cmd, entry in self.command_entries.items():
            self.command_mappings[cmd] = entry.get()
        self.log("All command mappings updated")
        self.save_config(show_log=False)

    def load_ui_settings(self):
        """Load UI settings from configuration"""
        # Set window geometry
        if self.config['window_geometry']:
            try:
                self.root.geometry(self.config['window_geometry'])
            except:
                pass

        # Set last used ports if available
        current_ports_list = [port.device for port in serial.tools.list_ports.comports()]

        # Microbit 1
        if self.config['last_ports'][0] in current_ports_list:
            self.port_var1.set(self.config['last_ports'][0])
        elif current_ports_list: # If last port not found, pick first available
            self.port_var1.set(current_ports_list[0])
        else: # No ports available
            self.port_var1.set("")

        # Microbit 2 (only if enabled and port_var2 is initialized)
        if self.second_microbit_enabled and hasattr(self, 'port_var2'):
            if self.config['last_ports'][1] in current_ports_list:
                self.port_var2.set(self.config['last_ports'][1])
            elif current_ports_list:
                # Try to set a different port than microbit 1
                available_port = next((p for p in current_ports_list if p != self.port_var1.get()), current_ports_list[0] if current_ports_list else '')
                if available_port:
                    self.port_var2.set(available_port)
                else:
                    self.port_var2.set("")
            else:
                self.port_var2.set("")


    def on_setting_changed(self, event=None):
        """Called when a setting is changed to auto-save"""
        # Auto-save after a short delay to avoid excessive saves
        if hasattr(self, '_save_timer'):
            self.root.after_cancel(self._save_timer)
        self._save_timer = self.root.after(2000, lambda: self.save_config(show_log=False))

    def refresh_ports(self):
        """Refresh the list of available COM ports for both microbits"""
        self.refresh_ports_for_microbit(0)
        if self.second_microbit_enabled:
            self.refresh_ports_for_microbit(1)

    def refresh_ports_for_microbit(self, microbit_index):
        """Refresh ports for a specific microbit"""
        ports = [port.device for port in serial.tools.list_ports.comports()]

        if microbit_index == 0:
            self.port_combo1['values'] = ports
            # Only update if current selection is not in new list or no selection
            if self.port_var1.get() not in ports and ports:
                self.port_var1.set(ports[0])
            elif not ports:
                self.port_var1.set("") # Clear selection if no ports
            self.port_combo1.bind('<<ComboboxSelected>>', self.on_setting_changed)
        elif self.second_microbit_enabled: # Check self.second_microbit_enabled here too
            # Ensure port_combo2 is initialized before accessing it
            if hasattr(self, 'port_combo2'):
                self.port_combo2['values'] = ports
                # Only update if current selection is not in new list or no selection
                if self.port_var2.get() not in ports and ports:
                    # Try to set a different port than microbit 1
                    available_port = next((p for p in ports if p != self.port_var1.get()), ports[0] if ports else '')
                    if available_port:
                        self.port_var2.set(available_port)
                    else: # No distinct port available or no ports at all
                        self.port_var2.set("")
                elif not ports:
                    self.port_var2.set("") # Clear selection if no ports
                self.port_combo2.bind('<<ComboboxSelected>>', self.on_setting_changed)


    def update_command_mapping(self, command):
        """Update a single command mapping"""
        self.command_mappings[command] = self.command_entries[command].get()
        # Auto-save after command change
        self.on_setting_changed()

    def log(self, message):
        """Add a message to the log"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        if self.log_text is not None:
            # Log widget is ready, write directly
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
            self.root.update_idletasks()
        else:
            # Log widget not ready yet, buffer the message
            self.log_buffer.append(log_entry)

    def flush_log_buffer(self):
        """Display all buffered log messages"""
        if self.log_text is not None and self.log_buffer:
            for entry in self.log_buffer:
                self.log_text.insert(tk.END, entry)
            self.log_text.see(tk.END)
            self.log_buffer.clear()
            self.root.update_idletasks()

    def clear_log(self):
        """Clear the log"""
        self.log_text.delete(1.0, tk.END)

    def toggle_connection(self, microbit_index):
        """
        Toggle serial connection for a specific microbit.
        If microbit_index is 0 and second microbit is enabled,
        it controls both Microbit 1 and Microbit 2.
        """
        if microbit_index == 0:
            if not self.is_running[0]: # If Microbit 1 is not running, try to start it (and maybe Microbit 2)
                self.start_server_single(0) # Start Microbit 1
                if self.second_microbit_enabled:
                    self.start_server_single(1) # Start Microbit 2 as well
            else: # Microbit 1 is running, so stop it (and maybe Microbit 2)
                self.stop_server(0) # Stop Microbit 1
                if self.second_microbit_enabled:
                    self.stop_server(1) # Stop Microbit 2 as well
        else: # microbit_index == 1, behave normally for Microbit 2
            if not self.is_running[microbit_index]:
                self.start_server_single(microbit_index)
            else:
                self.stop_server(microbit_index)


    def start_server_single(self, microbit_index):
        """Start the serial server for a specific microbit, including handshake."""
        try:
            if microbit_index == 0:
                port = self.port_var1.get()
                baud = int(self.baud_var1.get())
                connect_btn = self.connect_btn1
                status_label = self.status_label1
            else: # microbit_index == 1
                # Check if attributes exist before accessing them, in case Microbit 2 was just added
                if not self.second_microbit_enabled or not hasattr(self, 'port_var2') or not hasattr(self, 'baud_var2') or not hasattr(self, 'connect_btn2') or not hasattr(self, 'status_label2'):
                    self.log(f"Attempted to start Microbit 2 server but UI elements are not fully initialized or Microbit 2 is not enabled.")
                    return # Exit if Microbit 2 is not truly ready

                port = self.port_var2.get()
                baud = int(self.baud_var2.get())
                connect_btn = self.connect_btn2
                status_label = self.status_label2

            if not port:
                messagebox.showerror("Error", f"Please select a COM port for Microbit {microbit_index + 1}")
                return

            # Ensure any previous connection is closed first
            if self.serial_connections[microbit_index] and self.serial_connections[microbit_index].is_open:
                self.stop_server(microbit_index)

            # Open serial port
            ser = serial.Serial(port, baud, timeout=1)
            self.serial_connections[microbit_index] = ser

            self.log(f"[{port}] Posílám handshake…")
            ser.write(b"test\n") # Send handshake message

            handshake_success = False
            handshake_start_time = time.time()
            handshake_timeout = 5 # seconds

            while time.time() - handshake_start_time < handshake_timeout:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line == "OK":
                        self.log(f"[{port}] Handshake OK ✔")
                        handshake_success = True
                        break
                time.sleep(0.05) # Small delay to prevent busy-waiting

            if not handshake_success:
                self.log(f"[{port}] Handshake FAILED: No 'OK' received within {handshake_timeout} seconds.")
                ser.close()
                self.serial_connections[microbit_index] = None
                messagebox.showerror("Handshake Error", f"Microbit {microbit_index + 1} handshake failed. "
                                                         "Ensure Microbit is running the correct code "
                                                         "and sending 'OK' after 'test'.")
                # Reset UI state
                connect_btn.config(text="Start Server")
                status_label.config(text="Disconnected", foreground="red")
                self.is_running[microbit_index] = False
                return # Exit early if handshake failed

            # Handshake successful, proceed to start continuous reading
            self.is_running[microbit_index] = True

            # Start reading thread
            self.read_threads[microbit_index] = threading.Thread(
                target=self.read_serial, args=(microbit_index,), daemon=True)
            self.read_threads[microbit_index].start()

            # Update UI
            connect_btn.config(text="Stop Server")
            status_label.config(text="Connected", foreground="green")
            self.log(f"Microbit {microbit_index + 1} server started on {port} at {baud} baud")

        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Failed to connect Microbit {microbit_index + 1} to {port}: {str(e)}\n\n"
                                                     "Possible reasons:\n"
                                                     "- Port is already in use by another application.\n"
                                                     "- Microbit is not connected or drivers are not installed.\n"
                                                     "- Incorrect COM Port selected.")
            self.log(f"Microbit {microbit_index + 1} connection failed: {str(e)}")
            # Reset UI if connection fails (ensure attributes exist before configuring)
            if microbit_index == 0:
                self.connect_btn1.config(text="Start Server")
                self.status_label1.config(text="Disconnected", foreground="red")
            elif hasattr(self, 'connect_btn2') and hasattr(self, 'status_label2'):
                self.connect_btn2.config(text="Start Server")
                self.status_label2.config(text="Disconnected", foreground="red")
            self.is_running[microbit_index] = False # Ensure flag is reset
            if self.serial_connections[microbit_index]: # Close if it was opened but failed handshake
                self.serial_connections[microbit_index].close()
                self.serial_connections[microbit_index] = None
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error with Microbit {microbit_index + 1}: {str(e)}")
            self.log(f"Microbit {microbit_index + 1} error: {str(e)}")
            # Reset UI if connection fails (ensure attributes exist before configuring)
            if microbit_index == 0:
                self.connect_btn1.config(text="Start Server")
                self.status_label1.config(text="Disconnected", foreground="red")
            elif hasattr(self, 'connect_btn2') and hasattr(self, 'status_label2'):
                self.connect_btn2.config(text="Start Server")
                self.status_label2.config(text="Disconnected", foreground="red")
            self.is_running[microbit_index] = False # Ensure flag is reset
            if self.serial_connections[microbit_index]: # Close if it was opened but failed handshake
                self.serial_connections[microbit_index].close()
                self.serial_connections[microbit_index] = None


    def stop_server(self, microbit_index):
        """Stop the serial server for specific microbit"""
        self.is_running[microbit_index] = False # Signal the thread to stop

        # Give the read thread a moment to finish, if it's running
        if self.read_threads[microbit_index] and self.read_threads[microbit_index].is_alive():
            self.read_threads[microbit_index].join(timeout=0.5) # Wait a bit for it to naturally exit

        if self.serial_connections[microbit_index] and self.serial_connections[microbit_index].is_open:
            try:
                self.serial_connections[microbit_index].close()
                self.serial_connections[microbit_index] = None # Clear the reference
            except Exception as e:
                self.log(f"Error closing serial port for Microbit {microbit_index + 1}: {e}")

        # Update UI (ensure attributes exist before configuring)
        if microbit_index == 0:
            self.connect_btn1.config(text="Start Server")
            self.status_label1.config(text="Disconnected", foreground="red")
        elif hasattr(self, 'connect_btn2') and hasattr(self, 'status_label2'):
            self.connect_btn2.config(text="Start Server")
            self.status_label2.config(text="Disconnected", foreground="red")

        self.log(f"Microbit {microbit_index + 1} server stopped")

    def read_serial(self, microbit_index):
        """Read data from serial port in a separate thread"""
        ser = self.serial_connections[microbit_index]
        if not ser or not ser.is_open:
            self.log(f"Microbit {microbit_index + 1} read thread started but serial port is not open.")
            # This can happen if stop_server was called quickly after start_server failed handshake
            return

        while (self.is_running[microbit_index] and
               ser and
               ser.is_open):
            try:
                if ser.in_waiting > 0:
                    # Read until newline, then decode
                    line = ser.readline()
                    received_data = line.decode('utf-8', errors='ignore').strip() # Added error handling for decoding
                    if received_data:
                        self.process_command(received_data, microbit_index)
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
            except serial.SerialException:
                if self.is_running[microbit_index]: # Check flag to avoid logging on intentional stop
                    self.log(f"Microbit {microbit_index + 1} serial connection lost unexpectedly.")
                    # Use root.after to call stop_server on the main thread
                    self.root.after(0, lambda idx=microbit_index: self.stop_server(idx))
                break # Exit thread loop
            except Exception as e:
                self.log(f"Microbit {microbit_index + 1} read error: {str(e)}")
                # Consider stopping server on severe errors too
                if self.is_running[microbit_index]:
                    self.root.after(0, lambda idx=microbit_index: self.stop_server(idx))
                break # Exit thread loop


    def process_command(self, received_data, microbit_index):
        """Process received command from microbit"""
        self.log(f"Microbit {microbit_index + 1} received: '{received_data}'")

        # Determine the key to look up in command_mappings
        mapped_command = received_data
        if microbit_index == 1:
            # If it's Microbit 2, append '2' to the received command to match the keys
            mapped_command = received_data + "2"


        # Check if mapped command exists in our command mappings
        if mapped_command in self.command_mappings:
            command_to_execute = self.command_mappings[mapped_command]
            if command_to_execute.strip():  # Only execute if command is not empty
                self.execute_command(mapped_command, command_to_execute, microbit_index)
            else:
                self.log(f"No command assigned to '{mapped_command}' from Microbit {microbit_index + 1}")
        else:
            self.log(f"Unknown command from Microbit {microbit_index + 1}: '{received_data}' (looking for '{mapped_command}')")

    def execute_command(self, trigger, command, microbit_index):
        """Execute the assigned command"""
        try:
            self.log(f"Executing command for '{trigger}' from Microbit {microbit_index + 1}: {command}")

            # Execute command in a separate thread to avoid blocking
            def run_command():
                try:
                    # Use shell=True for Windows compatibility
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, check=False) # Added check=False to handle non-zero exit codes gracefully
                    if result.returncode == 0:
                        self.log(f"Command '{trigger}' from Microbit {microbit_index + 1} executed successfully")
                        if result.stdout:
                            self.log(f"Output: {result.stdout.strip()}")
                    else:
                        self.log(f"Command '{trigger}' from Microbit {microbit_index + 1} failed with return code {result.returncode}")
                        if result.stdout: # Log stdout even on error
                            self.log(f"Output (Error): {result.stdout.strip()}")
                        if result.stderr:
                            self.log(f"Error: {result.stderr.strip()}")
                except subprocess.TimeoutExpired:
                    self.log(f"Command '{trigger}' from Microbit {microbit_index + 1} timed out")
                except FileNotFoundError:
                    self.log(f"Error: Command '{command}' not found. Make sure it's in your system's PATH.")
                except Exception as e:
                    self.log(f"Failed to execute command '{trigger}' from Microbit {microbit_index + 1}: {str(e)}")

            threading.Thread(target=run_command, daemon=True).start()

        except Exception as e:
            self.log(f"Error initiating command execution for '{trigger}' from Microbit {microbit_index + 1}: {str(e)}")

    def on_closing(self):
        """Handle application closing"""
        for i in range(2):
            if self.is_running[i]:
                self.stop_server(i)
        # Save configuration before closing (silent save)
        self.save_config(show_log=False)
        self.root.destroy() # Ensure the root window is destroyed

if __name__ == "__main__":
    root = tk.Tk()
    app = MicrobitController(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing) # Handle graceful closing
    root.mainloop()
