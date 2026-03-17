# 🔹 Task 3: Service Monitor & Auto-Restart

## Goal:
Monitor if a process is running. If not, restart it.

## Example:
`procwatch --pid 34349`  
<!-- `procwatch --pidfile app.pid`  -->
`procwatch --match "python server.py"`  
`procwatch --port 8000`

## Requirements:
- Check every N seconds
- Log events
- Handle failures
- Timeout protection

## Multiple cli
`procwatch --match "python -m http.server 8000" --restart "python -m http.server 8000"`  
`procwatch --port 8000 --restart "/usr/bin/startmyapp" --interval 4`

## Skills Learned:
- Loop automation
- Subprocess execution
- Timeouts
- Basic watchdog design