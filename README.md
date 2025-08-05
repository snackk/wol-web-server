# Wake-on-LAN Web Interface

A Flask-based web application that provides a simple, secure interface for sending Wake-on-LAN packets to wake up remote devices, with integrated uptime monitoring using StatusCake.

## Features

- **Wake-on-LAN**: Send magic packets to wake up network devices remotely
- **Basic Authentication**: HTTP Basic Auth protection for secure access
- **Uptime Monitoring**: Visual uptime history chart powered by StatusCake API
- **Responsive Design**: Material Design Lite interface that works on desktop and mobile
- **Real-time Status**: Live uptime/downtime visualization with interactive charts

## Prerequisites

- Python 3.6+
- Flask
- wakeonlan
- requests

## Installation

1. Clone or download the application code
2. Install required dependencies:
3. `pip install flask wakeonlan requests`
 
 ## Configuration

The application requires several environment variables to be set:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MAC` | Target device MAC address | `00:11:22:33:44:55` |
| `IP` | Target device IP address | `192.168.1.100` |
| `WOL_USERNAME` | Authentication username | `admin` |
| `WOL_PASSWORD` | Authentication password | `secure_password` |

### Optional Variables (for uptime monitoring)

| Variable | Description |
|----------|-------------|
| `STATUSCAKE_API_KEY` | StatusCake API bearer token |
| `STATUSCAKE_TEST_ID` | StatusCake test ID for monitoring |

### Setting Environment Variables

**Linux/macOS:**
```
export MAC="00:11:22:33:44:55"
export IP="192.168.1.100"
export WOL_USERNAME="admin"
export WOL_PASSWORD="your_password"
export STATUSCAKE_API_KEY="your_api_key"
export STATUSCAKE_TEST_ID="your_test_id"
```

## Usage

1. Set the required environment variables
2. Run the application:
3. `python app.py`

3. Access the web interface at `http://localhost` (or your server's IP)
4. Log in with your configured credentials
5. Click the power button to send a Wake-on-LAN packet

Written by [@snackk](https://github.com/snackk).
