import socket, json

def send(cmd):
    s = socket.socket()
    s.connect(("<robot_ip>", 6666))
    s.send(json.dumps(cmd).encode("utf-8"))
    resp = s.recv(65536).decode("utf-8")
    s.close()
    return resp

print(send({"command":"execute_task",
            "language_instruction":"Open the left cabinet door",
            "actions_to_execute":120}))