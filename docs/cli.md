# CLI Reference

# Command

```bash
procwatch [OPTIONS]
```

---

## Options

| Option      | Description                       |
| ----------- | --------------------------------- |
| `--name`    | Filter processes by name          |
| `--port`    | Filter processes by port          |
| `--print`   | Print matching processes          |
| `--help`    | Show help message and exit        |
| `--version` | Show version information and exit |

---

## Examples

### List all processes

```bash
procwatch --print
```

### Filter by process name

```bash
procwatch --name sshd --print
```

### Filter by port

```bash
procwatch --port 22 --print
```

### Check web server (port 80)

```bash
procwatch --port 80 --print
```

### Run with elevated permissions

```bash
sudo $(which procwatch) --port 22 --print
```

---

## Notes

- Some system processes require elevated privileges to inspect.
- If a port is detected but `PID` is `None`, it is usually due to permission restrictions.
- In such cases, rerun the command with `sudo`.

---

## Exit Behavior

- Returns results when matching processes are found
- Prints a message if no matches are found
- Logs warnings/errors for permission-related issues
