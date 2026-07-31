"""Small, dependency-free utilities shared across pipeline scripts."""

import sys
import time


class ProgressBar:
    """A minimal terminal progress bar (no external dependency).

    Usage::

        bar = ProgressBar(total, desc='OpenAlex')
        for item in items:
            ...  # do work
            bar.update()          # advance by one
            bar.update(cached=True)  # advance, counting a cache hit
        bar.close()

    Renders a single self-updating line with percentage, counts, elapsed time,
    ETA, and (when relevant) how many items were served from cache. Falls back
    to periodic plain-text lines when stdout is not a TTY (e.g. piped to a log).
    """

    def __init__(self, total, desc='', stream=None, min_interval=0.1):
        self.total = int(total) if total else 0
        self.desc = desc
        self.stream = stream or sys.stdout
        self.min_interval = min_interval
        self.n = 0
        self.cached = 0
        self.errors = 0
        self.start = time.time()
        self._last_render = 0.0
        self._is_tty = bool(getattr(self.stream, 'isatty', lambda: False)())
        if self.total:
            self._render(force=True)

    def update(self, step=1, cached=False, error=False):
        self.n += step
        if cached:
            self.cached += step
        if error:
            self.errors += step
        self._render()

    def _format_eta(self, seconds):
        seconds = int(max(0, seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f'{h:d}h{m:02d}m'
        if m:
            return f'{m:d}m{s:02d}s'
        return f'{s:d}s'

    def _render(self, force=False):
        if not self.total:
            return
        now = time.time()
        done = self.n >= self.total
        if not force and not done and (now - self._last_render) < self.min_interval:
            return
        self._last_render = now
        frac = min(1.0, self.n / self.total)
        elapsed = now - self.start
        rate = self.n / elapsed if elapsed > 0 else 0
        eta = (self.total - self.n) / rate if rate > 0 else 0
        extra = []
        if self.cached:
            extra.append(f'cache {self.cached}')
        if self.errors:
            extra.append(f'err {self.errors}')
        extra_str = (' [' + ', '.join(extra) + ']') if extra else ''

        if self._is_tty:
            bar_len = 30
            filled = int(bar_len * frac)
            bar = '#' * filled + '-' * (bar_len - filled)
            line = (f'\r{self.desc} |{bar}| {self.n}/{self.total} '
                    f'({frac * 100:4.1f}%) ETA {self._format_eta(eta)}{extra_str}')
            self.stream.write(line)
            self.stream.flush()
        else:
            # Non-interactive: emit a line roughly every ~5% or on completion.
            step = max(1, self.total // 20)
            if done or self.n % step == 0:
                self.stream.write(
                    f'{self.desc} {self.n}/{self.total} ({frac * 100:.0f}%) '
                    f'ETA {self._format_eta(eta)}{extra_str}\n')
                self.stream.flush()

    def close(self):
        if self.total and self._is_tty:
            self.stream.write('\n')
            self.stream.flush()
