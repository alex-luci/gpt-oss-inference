# GPT-OSS Inference Project

A collection of Python scripts for interacting with GPT-OSS (Open Source GPT) models, featuring function calling capabilities for kitchen robot automation.

## Overview

This project contains various implementations for communicating with GPT-OSS models, with a focus on function calling for robotic kitchen assistance. The main implementation includes a chat interface that can execute robot commands through function calls.

## Files

- `gpt-oss-chat-function.py` - Main chat interface with function calling support for kitchen robot automation
- `gpt-oss-chat-api.py` - Basic API interface for GPT-OSS
- `gpt-oss-chat-api-memory.py` - API interface with conversation memory
- `gpt-oss-function-call.py` - Function calling implementation
- `gpt-oss-autonomous.py` - Autonomous operation script
- `state-machine.py` - State machine implementation
- `system-prompts.txt` - System prompts for different use cases
- `ui.txt` - User interface documentation

## Features

### Kitchen Robot Assistant
The main chat interface (`gpt-oss-chat-function.py`) provides:

- **Function Calling**: Native GPT-OSS function calling support
- **Kitchen Automation**: Commands for opening cabinets, moving items, adding ingredients
- **Physical Constraints**: Enforces kitchen safety rules and logical sequence
- **Interactive Chat**: Real-time conversation with the robot assistant

### Available Robot Commands
- Open/close cabinet doors
- Remove/replace pot lids
- Pick up and place pineapples
- Add salt to recipes
- Get robot status

## Requirements

- Python 3.7+
- requests library
- GPT-OSS model running on localhost:11434
- Robot control server on localhost:7000

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install requests
   ```
3. Ensure GPT-OSS is running on localhost:11434
4. Ensure robot control server is running on localhost:7000

## Usage

Run the main chat interface:
```bash
python gpt-oss-chat-function.py
```

The interface will guide you through available commands and help you interact with the kitchen robot.

## Architecture

The project uses a modular approach:
- **Communication Layer**: Socket-based communication with robot control server
- **API Layer**: HTTP requests to GPT-OSS API
- **Function Layer**: Function calling implementation for robot commands
- **Chat Layer**: Interactive conversation interface

## Development

This project is designed for experimentation with GPT-OSS function calling capabilities in a kitchen automation context. The codebase includes multiple approaches to function calling and conversation management.

## License

This project is for experimental and educational purposes.
