# Specific Tool 🎯

Specific Tool is a high-performance input optimization and peripheral management tool designed for competitive gaming. It automates DPI switching, polling rate adjustments, and digital vibrance settings based on the active process.

## 🚀 Key Features

- **Murqin Mode (Input Normalization):** Implements a mathematical transfer function to allow **High Hardware DPI (e.g., 1600)** paired with **Low Software Sensitivity**. This reduces sensor noise and jitter while maintaining the user's preferred cursor speed (e.g., 800 eDPI feel).

- **Bus Contention Safety:** Features a robust packet queue system with debounce logic to prevent USB HID write collisions during rapid state changes (Alt-Tab).

- **Emergency Exit Protocol:** Global `atexit` hooks ensure hardware (Mouse MCU) and OS settings (Windows Pointer Speed) always revert to safe defaults upon crash or closure.

- **Process-Aware Automation:** Automatically detects games to apply:
  - 1600 DPI / 8000Hz Polling Rate (Game Mode)
  - 100% Digital Vibrance (Nvidia)
  - Reverts to 800 DPI / 1000Hz / 50% Vibrance on Desktop.

## 🛠️ Technology Stack

- **Python 3.9**
- **Win32 API (ctypes, pywin32):** Direct Kernel-level mouse sensitivity manipulation.
- **HIDAPI:** Raw USB communication for mouse MCU configuration.
- **CustomTkinter:** Modern, high-DPI aware UI.

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/murqin/specific-tool.git](https://github.com/Murqin/specific-tool.git)


## 🧪 For Developers: Porting to Other Mice

Currently, the `MouseBackend` class is hardcoded with **VXE MAD R** specific USB HID reports. However, the architecture is modular and can be adapted for any mouse that accepts HID commands.

If you want to port this tool to your own mouse (e.g., Logitech, Razer, Lamzu), follow these steps:

1.  **Sniff USB Traffic:** Use tools like **Wireshark** (with USBPcap) to capture packets while changing DPI and Polling Rate in your mouse's official software.
2.  **Analyze Hex Dumps:** Identify the specific `SET_REPORT` sequences sent to the device during these changes.
3.  **Update Constants:** Modify the following variables in `src/main.py`:

    ```python
    # In class MouseBackend:
    self.VENDOR_ID = 0xYOUR_VID
    self.PRODUCT_ID = 0xYOUR_PID

    # Update Command Arrays (Example)
    CMD_HZ_8000 = [0xDE, 0xAD, 0xBE, 0xEF, ...] # Your 8KHz Hex Sequence
    SEQ_DPI_1600 = [[0x01, ...], [0x02, ...]]    # Your DPI Switch Sequence
    ```

> **Tip:** If your mouse requires a specific "Handshake" or "Unlock" sequence before accepting commands, ensure you send those packets first in the `connect()` method.