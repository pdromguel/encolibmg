# Security

## Reporting a vulnerability
Please **don't open a public issue**. Use GitHub's private reporting instead:
**Security → Report a vulnerability** on this repository. You'll get an answer as soon as possible.

## Scope
EncoLibMG runs locally. Things that matter most:
- the local server that feeds the window (`127.0.0.1`, random port, per-run token) and its `/media` route,
  which may only serve files inside the open library;
- file operations (rename, remove, import, fixes) staying inside the library folder;
- links opened from the app (only `https://` YouTube links are allowed);
- downloaded content handled by ffmpeg and yt-dlp.

## Supported versions
Only the latest release gets fixes.
