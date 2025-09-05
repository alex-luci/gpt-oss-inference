# GPT-OSS Kitchen Assistant UI

A fully autonomous kitchen assistant powered by GPT-OSS with real-time task planning, execution tracking, and state management. The application provides a modern Tkinter interface for interacting with a local GPT-OSS model that can control a kitchen robot through function calling.

## Features

- **GPT-OSS Integration**: Communicates with a local GPT-OSS model (e.g., Ollama) at `http://localhost:11434`
- **Function Calling**: GPT-OSS can call 6 different functions for complete kitchen automation
- **Autonomous Planning**: GPT-OSS creates its own task plans and executes them step-by-step
- **Real-time State Management**: Tracks kitchen state (cabinet, lid, pineapple, salt) with live updates
- **Interactive UI**: Modern chat interface with status panels, task checklist, and kitchen state display
- **Thread-safe Updates**: Smooth UI updates using background threads and queues
- **No Hardcoded Logic**: GPT-OSS has complete autonomy in planning, execution, and state management

## Available Functions

GPT-OSS can call these functions to control the kitchen:

1. **`execute_robot_command(language_instruction, use_angle_stop=True)`**
   - Controls the robot with natural language instructions
   - Fixed to 150 actions per command for consistent execution
   - Supports all kitchen operations (open/close cabinet, handle lid, place pineapple, add salt)

2. **`get_robot_status()`**
   - Checks current robot status and connectivity

3. **`update_kitchen_state(state_updates)`**
   - Updates the internal kitchen state (cabinet_open, lid_on_pot, pineapple_in_pot, salt_added)
   - Triggers real-time UI updates

4. **`mark_task_complete(task_id)`**
   - Marks specific tasks as completed in the checklist
   - Updates the task list display

5. **`get_current_plan()`**
   - Retrieves the current task plan and kitchen state
   - Useful for GPT-OSS to check its progress

6. **`create_plan(tasks)`**
   - Creates a new task plan from a list of task descriptions
   - Displays tasks in the checklist with checkboxes
   - Required before executing any kitchen tasks

## UI Components

### Chat Panel (Left)
- **Chat History**: Scrollable conversation with GPT-OSS
- **Input Field**: Type messages and press Enter or click Send
- **Styled Messages**: User messages in blue, assistant responses in gray

### Status Panel (Right)
- **Robot Status**: Current robot connectivity and status
- **User Task**: The current user request being processed
- **Executing**: The specific robot command currently running
- **Next Step**: The next pending task from the plan

### Task Checklist
- **Dynamic Tasks**: Shows tasks created by GPT-OSS via `create_plan()`
- **Progress Tracking**: Checkboxes (☐/☑) show completion status
- **Clean Descriptions**: Displays only task descriptions, not JSON objects

### Kitchen State Display
- **Cabinet Open**: Yes/No status
- **Lid On Pot**: Yes/No status  
- **Pineapple In Pot**: Yes/No status
- **Salt Added**: Yes/No status
- **Real-time Updates**: Changes as GPT-OSS calls `update_kitchen_state()`

## Requirements

- **Python 3.8+**
- **Dependencies**: `requests` (for GPT-OSS API calls)
- **GPT-OSS Server**: Running at `http://localhost:11434` (Ollama-compatible)
- **Robot Server**: Listening on `localhost:7000` (TCP socket for robot commands)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/alex-luci/gpt-oss-inference.git
cd gpt-oss-inference
```

2. Install dependencies:
```bash
pip install requests
```

3. Start your GPT-OSS server (e.g., Ollama):
```bash
ollama serve
ollama pull gpt-oss:20b  # or your preferred model
```

4. Start your robot control server on port 7000

## Usage

1. Run the application:
```bash
python gpt-oss-chat-function-ui.py
```

2. Type a kitchen task request, for example:
   - "Make a pineapple smoothie"
   - "Add salt to the pot"
   - "Open the cabinet and get the pineapple"

3. Watch GPT-OSS:
   - Create a task plan
   - Execute robot commands in the correct order
   - Update kitchen state after each action
   - Mark tasks complete as they finish
   - Adapt if conditions change

## How It Works (Autonomous Mode)

### GPT-OSS Autonomy
The core `GPTOSSChatBot` class provides complete autonomy to GPT-OSS:

1. **Plan Creation**: GPT-OSS must call `create_plan()` before executing any tasks
2. **State Management**: GPT-OSS manages its own `kitchen_state` using `update_kitchen_state()`
3. **Task Execution**: GPT-OSS calls `execute_robot_command()` for each robot action
4. **Progress Tracking**: GPT-OSS calls `mark_task_complete()` when tasks finish
5. **Adaptive Planning**: GPT-OSS can modify plans based on real conditions

### No Hardcoded Logic
The application contains **zero hardcoded logic**:
- No preconditions or guards in the code
- No automatic task sequencing
- No heuristic state updates
- No forced step ordering
- GPT-OSS makes all decisions autonomously

### Physical Constraints
GPT-OSS is aware of these constraints through its system prompt:
- Cannot access pineapple unless cabinet door is open
- Cannot put pineapple in pot if lid is on pot
- Cannot add salt if lid is on pot
- Must close cabinet door after removing items
- Must put lid back on pot at the end (for smoothie tasks)

### Example Workflow
1. User: "Make a pineapple smoothie"
2. GPT-OSS calls `create_plan()` with 5 tasks
3. GPT-OSS calls `execute_robot_command("Open the left cabinet door")`
4. GPT-OSS calls `update_kitchen_state({"cabinet_open": True})`
5. GPT-OSS calls `mark_task_complete(1)`
6. GPT-OSS continues with next task...
7. UI updates in real-time showing progress

## Architecture

### GPTOSSChatBot Class
- **Function Registry**: Maps function names to Python methods
- **State Management**: Maintains `kitchen_state` and `task_list`
- **API Communication**: Handles GPT-OSS API calls with tool calling
- **Error Handling**: Robust error handling for all function calls

### KitchenAssistantUI Class
- **Thread-safe Updates**: Uses queues for UI updates from background threads
- **Real-time Display**: Updates checklist, status, and kitchen state instantly
- **Modern Styling**: Clean, professional UI with proper typography and colors
- **Responsive Layout**: PanedWindow with chat and status panels

### Communication Flow
```
User Input → GPT-OSS API → Function Calls → Robot Commands → State Updates → UI Updates
```

## Customization

### System Prompt
Edit `_get_system_prompt()` to modify GPT-OSS behavior, add constraints, or change instructions.

### Function Tools
Modify the `tools` array in `_call_gpt_oss()` to add new functions or change existing ones.

### UI Styling
Update the `ttk.Style` configurations in `KitchenAssistantUI.__init__()` to change colors, fonts, or layout.

### Robot Integration
Modify the `send()` function to integrate with different robot control protocols or APIs.

## Troubleshooting

### GPT-OSS Connection Issues
- Ensure Ollama is running: `ollama serve`
- Check model availability: `ollama list`
- Verify API endpoint: `http://localhost:11434`

### Robot Connection Issues
- Ensure robot server is running on port 7000
- Check robot server logs for connection attempts
- Verify JSON command format matches robot expectations

### UI Issues
- Check Python version (3.8+ required)
- Ensure tkinter is available: `python -m tkinter`
- Verify all dependencies are installed

## Development

The codebase is structured for easy extension:

- **Add New Functions**: Add methods to `GPTOSSChatBot` and register them in `available_functions`
- **Add UI Components**: Extend `KitchenAssistantUI` with new panels or displays
- **Modify Robot Protocol**: Update the `send()` function for different robot APIs
- **Enhance State Management**: Add new state variables and UI displays

## License

Experimental/educational use only.

## Contributing

This is a focused, single-purpose application. For major changes, consider creating a fork or separate repository.
