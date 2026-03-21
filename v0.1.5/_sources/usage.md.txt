# Usage

## List all processes

```bash
procwatch --print
```

## Filter by process name
```bash
procwatch --name sshd --print
```

## Filter by port
```bash
procwatch --port 22 --print
```

## Notes
- Some system processes require sudo to inspect fully.
- If PID is not visible, it may be due to permission restrictions.