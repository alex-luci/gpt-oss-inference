import json
import socket
import requests
from typing import Dict, Any, List, Callable, Optional
import threading
import queue
import time
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk

def send(cmd):
    """Function that GPT-OSS will call"""
    s = socket.socket()
    s.connect(("localhost", 7000))
    s.send(json.dumps(cmd).encode("utf-8"))
    resp = s.recv(65536).decode("utf-8")
    s.close()
    return resp

class GPTOSSChatBot:
    def __init__(self,
                 on_assistant_message: Optional[Callable[[str], None]] = None,
                 on_tool_result: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                 on_status_update: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_plan_update: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
                 on_execute_start: Optional[Callable[[str], None]] = None):
        self.gpt_oss_url = "http://localhost:11434/api/chat"
        self.conversation_history = []
        self.available_functions = {
            "execute_robot_command": self.execute_robot_command,
            "get_robot_status": self.get_robot_status
        }
        
        # UI callbacks
        self.on_assistant_message = on_assistant_message
        self.on_tool_result = on_tool_result
        self.on_status_update = on_status_update
        self.on_plan_update = on_plan_update
        self.on_execute_start = on_execute_start
        
        # State tracking
        self.last_robot_status: Optional[Dict[str, Any]] = None
        self.current_task: Optional[str] = None
        self.current_user_task_text: Optional[str] = None
        self.task_list: List[Dict[str, Any]] = []  # [{"id": 1, "title": str, "done": bool}]
        self.kitchen_state: Dict[str, Any] = {
            "cabinet_open": False,
            "lid_on_pot": True,
            "pineapple_in_pot": False,
            "salt_added": False
        }
        
        # Initialize with system prompt that enables function calling
        self.conversation_history = [{
            "role": "system",
            "content": self._get_system_prompt()
        }]
    
    def _get_system_prompt(self):
        return """You are a kitchen assistant helping to make a pineapple smoothie. You must follow the physical constraints of the kitchen and use actions in the correct sequence.

## Kitchen Layout
- **Left**: Cabinet (currently closed) containing a pineapple
- **Center**: Pot with lid on top
- **Right**: Salt shaker

## Available Functions & Actions
You can execute these robot actions using the execute_robot_command function:
- "Open the left cabinet door"
- "Close the left cabinet door"
- "Take off the lid from the gray recipient and place it on the counter"
- "Pick up the lid from the counter and put it on the gray recipient"
- "Pick up the green pineapple from the left cabinet and place it in the gray recipient"
- "Put salt in the gray recipient"

## Physical Constraints
1. Cannot access pineapple unless cabinet door is open
2. Cannot put pineapple in pot if lid is on the pot
3. Cannot add salt if lid is on the pot
4. Must close cabinet door after removing items (kitchen safety)
5. Must put lid back on pot at the end
6. **Salt rule**: Only add salt if the user explicitly requests it - do not add salt unless told to do so

## Your Process
1. **Analyze** the current kitchen state and user request
2. **Plan** the sequence of actions needed following physical constraints
3. **Execute** each action using the execute_robot_command function
4. **Verify** completion and provide status updates
5. **Handle** any errors and replan if necessary

## Decision Making Examples

**User**: "Make a pineapple smoothie"
**Your Response**: "I'll help you make a pineapple smoothie! Let me break this down:
1. First, I need to open the cabinet to access the pineapple
2. Then remove the pot lid so I can add ingredients
3. Get the pineapple and put it in the pot
4. Close the cabinet for safety
5. Put the lid back on

Let me start by opening the cabinet door."
*[Then call execute_robot_command with "Open the left cabinet door"]*

**User**: "What's happening?"
**Your Response**: "Let me check the robot status for you."
*[Then call get_robot_status function]*

## Key Behaviors
- **Be proactive**: If a task requires multiple steps, plan and execute them all
- **Be safe**: Always follow physical constraints
- **Be communicative**: Explain your plan before executing
- **Be adaptive**: If something fails, replan and try alternative approaches
- **Be thorough**: Complete entire tasks, not just single actions
- **Execute step-by-step**: Use execute_robot_command for each physical action needed

## Function Usage
- Use execute_robot_command(language_instruction, actions_to_execute=150, use_angle_stop=True) for robot actions
- Use get_robot_status() to check robot status when needed
- Always explain what you're doing before calling functions
- Wait for function results before planning next steps

Remember: The final state should have the cabinet door closed and the lid back on the pot. Take initiative and complete tasks end-to-end using the available functions!"""

    def execute_robot_command(self, language_instruction: str, actions_to_execute: int = 150, use_angle_stop: bool = True):
        """Execute a command on the robot"""
        self.current_task = language_instruction
        # Notify UI execution start
        if self.on_execute_start:
            try:
                self.on_execute_start(language_instruction)
            except Exception:
                pass
        
        cmd = {
            "command": "execute_task",
            "language_instruction": language_instruction,
            "actions_to_execute": actions_to_execute,
            "use_angle_stop": True
        }
        
        try:
            result = send(cmd)
            payload = {
                "status": "success",
                "result": result,
                "instruction": language_instruction,
                "use_angle_stop": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            if self.on_tool_result:
                self.on_tool_result("execute_robot_command", payload)
            return payload
        except Exception as e:
            payload = {
                "status": "error",
                "error": str(e),
                "instruction": language_instruction,
                "use_angle_stop": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if self.on_tool_result:
                self.on_tool_result("execute_robot_command", payload)
            return payload
    
    def get_robot_status(self):
        """Get current robot status"""
        cmd = {"command": "get_status"}
        try:
            result = send(cmd)
            payload = {"status": "success", "robot_status": result, "timestamp": datetime.now(timezone.utc).isoformat()}
            self.last_robot_status = payload
            if self.on_tool_result:
                self.on_tool_result("get_robot_status", payload)
            if self.on_status_update:
                self.on_status_update(payload)
            return payload
        except Exception as e:
            payload = {"status": "error", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
            if self.on_tool_result:
                self.on_tool_result("get_robot_status", payload)
            if self.on_status_update:
                self.on_status_update(payload)
            return payload
    
    def chat(self, user_message: str) -> str:
        """Main chat function - handles user input and returns response"""
        
        # Add user message to conversation
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })
        self.current_task = user_message
        self.current_user_task_text = user_message
        
        # Directly call GPT-OSS and let it decide how to proceed (tools vs. text)
        # No pre-status calls, no injected kitchen state, no pre-planning
        
        # Get GPT-OSS response loop
        gpt_response = self._call_gpt_oss()
        
        # No need to call on_assistant_message here (_call_gpt_oss handles it)
        return gpt_response

    def _plan_tasks(self, user_message: str) -> List[Dict[str, Any]]:
        """Planner disabled: return empty list and let the model drive planning in free-form."""
        return []
    
    def _call_gpt_oss(self) -> str:
        """Call GPT-OSS API with function calling support in a loop until tasks complete"""
        
        # Define available tools for GPT-OSS
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_robot_command",
                    "description": "Execute a command on the kitchen robot",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "language_instruction": {
                                "type": "string",
                                "description": "Natural language instruction for the robot"
                            },
                            "actions_to_execute": {
                                "type": "integer",
                                "description": "Number of actions to execute (default: 150)",
                                "default": 150
                            },
                            "use_angle_stop": {
                                "type": "boolean",
                                "description": "Whether to use angle stop (default: true)",
                                "default": True
                            }
                        },
                        "required": ["language_instruction"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_robot_status",
                    "description": "Get the current status of the robot",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        
        max_steps = 20
        step = 0
        
        try:
            while step < max_steps:
                step += 1
                print(f"🔍 Calling GPT-OSS (step {step}) with tools enabled...")
                
                payload = {
                    "model": "gpt-oss:20b",
                    "messages": self.conversation_history,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": False
                }
                
                response = requests.post(self.gpt_oss_url, json=payload, timeout=30)
                
                if response.status_code != 200:
                    print(f"❌ HTTP Error: {response.status_code}")
                    return f"HTTP Error {response.status_code}: {response.text}"
                
                result = self._parse_gpt_response(response.text)
                message = result.get("message", {})
                
                # Get the text content
                content = message.get("content", "")
                
                # Check for tool calls
                tool_calls = message.get("tool_calls", [])
                
                # Retry once if both are empty
                if not content and not tool_calls:
                    print("⚠️ Empty reply from model; retrying once...")
                    retry_payload = dict(payload)
                    # Nudge with a small assistant reminder
                    self.conversation_history.append({"role": "assistant", "content": "Continue with the next step following constraints."})
                    retry_payload["messages"] = self.conversation_history
                    response = requests.post(self.gpt_oss_url, json=retry_payload, timeout=30)
                    if response.status_code == 200:
                        result = self._parse_gpt_response(response.text)
                        message = result.get("message", {})
                        content = message.get("content", "")
                        tool_calls = message.get("tool_calls", [])
                
                if tool_calls:
                    print(f"🔧 GPT-OSS wants to call {len(tool_calls)} function(s) (step {step})")
                    
                    # Execute tool calls
                    tool_results = []
                    for i, tool_call in enumerate(tool_calls):
                        function_name = tool_call["function"]["name"]
                        function_args = tool_call["function"].get("arguments", {})
                        
                        print(f"🤖 Calling: {function_name}({function_args})")
                        
                        if function_name in self.available_functions:
                            try:
                                # Some providers pass arguments as JSON strings
                                if isinstance(function_args, str):
                                    try:
                                        function_args = json.loads(function_args)
                                    except Exception:
                                        # keep as-is if not a JSON string
                                        pass
                                result_payload = self.available_functions[function_name](**function_args)
                                tool_results.append(result_payload)
                                print(f"✅ Function result: {result_payload}")
                            except Exception as e:
                                error_result = {"status": "error", "error": str(e)}
                                tool_results.append(error_result)
                                print(f"❌ Function error: {e}")
                        else:
                            unknown_result = {"status": "error", "error": f"Unknown function: {function_name}"}
                            tool_results.append(unknown_result)
                            print(f"❌ Unknown function: {function_name}")
                    
                    # Add assistant message with tool calls to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls
                    })
                    
                    # Add tool results to history
                    for i, (tool_call, result_payload) in enumerate(zip(tool_calls, tool_results)):
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": f"call_{i}",
                            "name": tool_call["function"]["name"],
                            "content": json.dumps(result_payload)
                        })
                    
                    # Continue loop to let the model observe tool results and decide next actions
                    continue
                else:
                    # No tool calls, just regular response — assume completion
                    if content:
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": content
                        })
                        print(f"🤖 Assistant: {content}")
                        if self.on_assistant_message:
                            self.on_assistant_message(content)
                        return content
                    else:
                        print("❌ No content or tool calls in response")
                        return "I didn't understand that. Can you try again?"
            
            # Safety valve to prevent infinite loops
            print("⚠️ Reached maximum step limit without a final answer.")
            return "I executed many steps but reached the maximum step limit. If there's more to do, please continue."
        except Exception as e:
            error_msg = f"Error calling GPT-OSS: {e}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def _parse_gpt_response(self, response_text: str) -> Dict:
        """Parse GPT-OSS response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            return {"message": {"content": response_text}}

# --------------------------
# Tkinter UI
# --------------------------
class KitchenAssistantUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Kitchen Robot Assistant (GPT-OSS)")
        self.root.geometry("1100x700")
        
        # Global style
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        
        style.configure("Title.TLabel", font=("Inter", 15, "bold"))
        style.configure("Subtitle.TLabel", font=("Inter", 11))
        style.configure("Section.TLabelframe", background="#F7F8FA")
        style.configure("Section.TLabelframe.Label", font=("Inter", 12, "bold"))
        style.configure("TButton", font=("Inter", 10))
        style.configure("Accent.TButton", font=("Inter", 10, "bold"))
        
        self.root.configure(bg="#EEF1F5")
        
        # Queues for thread-safe UI updates
        self.message_queue: "queue.Queue[str]" = queue.Queue()
        self.status_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.plan_queue: "queue.Queue[List[Dict[str, Any]]]" = queue.Queue()
        self.exec_queue: "queue.Queue[str]" = queue.Queue()
        
        # Build layout: PanedWindow with left chat, right status
        paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        
        left_frame = ttk.Frame(paned)
        right_frame = ttk.Frame(paned, width=380)
        paned.add(left_frame, weight=3)
        paned.add(right_frame, weight=2)
        
        # Left: chat panel (container)
        chat_container = ttk.Labelframe(left_frame, text="Chat", style="Section.TLabelframe")
        chat_container.pack(fill=tk.BOTH, expand=True)
        
        header_row = ttk.Frame(chat_container)
        header_row.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(header_row, text="Kitchen Assistant", style="Title.TLabel").pack(side=tk.LEFT)
        
        # Chat history with scrollbar
        chat_box_frame = ttk.Frame(chat_container)
        chat_box_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.chat_history = tk.Text(chat_box_frame, wrap=tk.WORD, bg="#FFFFFF", relief=tk.FLAT,
                                    font=("Inter", 11))
        self.chat_history.configure(state=tk.DISABLED)
        chat_scroll = ttk.Scrollbar(chat_box_frame, orient=tk.VERTICAL, command=self.chat_history.yview)
        self.chat_history.configure(yscrollcommand=chat_scroll.set)
        self.chat_history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text tags for pretty chat
        self.chat_history.tag_configure("user_prefix", foreground="#0B5FFF", font=("Inter", 11, "bold"))
        self.chat_history.tag_configure("assistant_prefix", foreground="#6B7280", font=("Inter", 11, "bold"))
        self.chat_history.tag_configure("user_text", foreground="#111827")
        self.chat_history.tag_configure("assistant_text", foreground="#111827")
        
        # Input row
        input_row = ttk.Frame(chat_container)
        input_row.pack(fill=tk.X, padx=12, pady=(0, 12))
        self.user_input = ttk.Entry(input_row)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.user_input.bind("<Return>", lambda e: self.send_message())
        ttk.Button(input_row, text="Send", style="Accent.TButton", command=self.send_message).pack(side=tk.LEFT, padx=8)
        
        # Right: status panel
        status_container = ttk.Labelframe(right_frame, text="Status & Activity", style="Section.TLabelframe")
        status_container.pack(fill=tk.BOTH, expand=True)
        
        # Status labels
        meta_frame = ttk.Frame(status_container)
        meta_frame.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(meta_frame, text="Robot Status:", style="Subtitle.TLabel").grid(row=0, column=0, sticky="w")
        self.status_value_var = tk.StringVar(value="Unknown")
        ttk.Label(meta_frame, textvariable=self.status_value_var, font=("Inter", 11, "bold")).grid(row=0, column=1, sticky="w", padx=6)
        
        ttk.Label(meta_frame, text="User Task:", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.current_user_task_var = tk.StringVar(value="-")
        ttk.Label(meta_frame, textvariable=self.current_user_task_var, foreground="#0B5FFF", font=("Inter", 11, "bold")).grid(row=1, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(meta_frame, text="Executing:", style="Subtitle.TLabel").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.current_executing_var = tk.StringVar(value="-")
        ttk.Label(meta_frame, textvariable=self.current_executing_var, font=("Inter", 11, "bold")).grid(row=2, column=1, sticky="w", padx=6, pady=(6, 0))
        
        ttk.Label(meta_frame, text="Next Step:", style="Subtitle.TLabel").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.current_task_var = tk.StringVar(value="-")
        ttk.Label(meta_frame, textvariable=self.current_task_var, font=("Inter", 11)).grid(row=3, column=1, sticky="w", padx=6, pady=(6, 0))
        
        # Checklist
        checklist_frame = ttk.Frame(status_container)
        checklist_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 6))
        ttk.Label(checklist_frame, text="Checklist", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))
        columns = ("done", "task")
        self.task_tree = ttk.Treeview(checklist_frame, columns=columns, show="headings", height=14)
        self.task_tree.heading("done", text="Done")
        self.task_tree.heading("task", text="Task")
        self.task_tree.column("done", width=60, anchor="center")
        self.task_tree.column("task", anchor="w")
        tree_scroll = ttk.Scrollbar(checklist_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=tree_scroll.set)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        status_buttons = ttk.Frame(status_container)
        status_buttons.pack(anchor="e", padx=12, pady=(0, 12))
        ttk.Button(status_buttons, text="Refresh Status", command=self.refresh_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(status_buttons, text="Clear Checklist", command=self.clear_checklist).pack(side=tk.LEFT, padx=5)
        
        # Instantiate bot with callbacks
        self.bot = GPTOSSChatBot(
            on_assistant_message=self._on_assistant_message,
            on_tool_result=self._on_tool_result,
            on_status_update=self._on_status_update,
            on_plan_update=self._on_plan_update,
            on_execute_start=self._on_execute_start
        )
        
        # Initial status load
        self.refresh_status()
        
        # Poll queues for UI updates
        self._poll_queues()
    
    def append_chat(self, text: str, who: str):
        self.chat_history.configure(state=tk.NORMAL)
        if who == "user":
            self.chat_history.insert(tk.END, "👤 You: ", ("user_prefix",))
            self.chat_history.insert(tk.END, f"{text}\n", ("user_text",))
        else:
            self.chat_history.insert(tk.END, "🤖 Assistant: ", ("assistant_prefix",))
            self.chat_history.insert(tk.END, f"{text}\n", ("assistant_text",))
        self.chat_history.see(tk.END)
        self.chat_history.configure(state=tk.DISABLED)
    
    def render_plan(self, tasks: List[Dict[str, Any]]):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        for t in tasks:
            mark = "☑" if t.get("done") else "☐"
            self.task_tree.insert("", tk.END, iid=str(t.get("id")), values=(mark, t.get("title", "")))
    
    def clear_checklist(self):
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
    
    def refresh_status(self):
        def worker():
            status = self.bot.get_robot_status()
            self.status_queue.put(status)
        threading.Thread(target=worker, daemon=True).start()
    
    def clear_status(self):
        self.status_value_var.set("-")
    
    def send_message(self):
        text = self.user_input.get().strip()
        if not text:
            return
        self.user_input.delete(0, tk.END)
        self.append_chat(text, who="user")
        self.current_user_task_var.set(text)
        self.current_executing_var.set("-")
        
        def worker():
            reply = self.bot.chat(text)
            # Do not enqueue reply here; the bot already enqueues via on_assistant_message
            _ = reply
        threading.Thread(target=worker, daemon=True).start()
    
    # Bot callback handlers (thread-safe: push to queues)
    def _on_assistant_message(self, message: str):
        self.message_queue.put(message)
    
    def _on_tool_result(self, name: str, payload: Dict[str, Any]):
        if name == "execute_robot_command":
            # Do not hardcode task completion; the model should drive updates
            # Optionally, the model can emit plan updates as assistant messages which we render
            pass
        elif name == "get_robot_status":
            # status panel handled in _on_status_update
            pass

    def _on_status_update(self, payload: Dict[str, Any]):
        self.status_queue.put(payload)
    
    def _on_plan_update(self, plan: List[Dict[str, Any]]):
        self.plan_queue.put(plan)

    def _on_execute_start(self, instruction: str):
        # Called from bot thread; queue to UI thread
        self.exec_queue.put(instruction)
    
    def _poll_queues(self):
        # Messages
        try:
            while True:
                msg = self.message_queue.get_nowait()
                if isinstance(msg, str):
                    self.append_chat(msg, who="assistant")
        except queue.Empty:
            pass
        
        # Status updates
        try:
            while True:
                status = self.status_queue.get_nowait()
                # Update label with a concise status string
                if isinstance(status, dict) and status.get("status") == "success":
                    robot_status = status.get("robot_status")
                    if isinstance(robot_status, str):
                        self.status_value_var.set(robot_status[:64] + ("…" if len(robot_status) > 64 else ""))
                    else:
                        self.status_value_var.set("OK")
                elif isinstance(status, dict) and status.get("status") == "error":
                    self.status_value_var.set(f"Error: {status.get('error')}")
                else:
                    self.status_value_var.set("Unknown")
        except queue.Empty:
            pass
        
        # Plan updates
        try:
            while True:
                plan = self.plan_queue.get_nowait()
                if isinstance(plan, list):
                    self.render_plan(plan)
                    next_task = next((t for t in plan if not t.get("done")), None)
                    self.current_task_var.set(next_task["title"] if next_task else "All tasks complete")
        except queue.Empty:
            pass
        
        # Executing updates
        try:
            while True:
                instr = self.exec_queue.get_nowait()
                self.current_executing_var.set(instr)
        except queue.Empty:
            pass
        
        self.root.after(100, self._poll_queues)

# Interactive Chat Interface (Tkinter)
def main():
    root = tk.Tk()
    app = KitchenAssistantUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()