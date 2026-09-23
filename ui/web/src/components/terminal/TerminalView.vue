<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { Unicode11Addon } from '@xterm/addon-unicode11'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { RefreshCw } from 'lucide-vue-next'
import { socketUrl } from '@/api/http'
import { usePrefs } from '@/stores/prefs'

/**
 * A live terminal attached to a tmux session through the server's PTY bridge. Interactive mode
 * sends keystrokes to the agent; read-only mode attaches as a watcher that cannot type.
 */
const props = withDefaults(defineProps<{ session: string; mode?: 'interactive' | 'readonly'; autofocus?: boolean }>(), {
  mode: 'interactive',
  autofocus: false,
})
const emit = defineEmits<{ status: [state: 'connecting' | 'ready' | 'closed' | 'error', message: string] }>()

const container = ref<HTMLDivElement>()
const state = ref<'connecting' | 'ready' | 'closed' | 'error'>('connecting')
const message = ref('')
const prefs = usePrefs()
let terminal: Terminal | null = null
let fit: FitAddon | null = null
let socket: WebSocket | null = null
let observer: ResizeObserver | null = null
let resizeTimer: number | undefined
const encoder = new TextEncoder()

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function theme() {
  const names = [
    'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
    'brightBlack', 'brightRed', 'brightGreen', 'brightYellow', 'brightBlue', 'brightMagenta', 'brightCyan', 'brightWhite',
  ] as const
  const palette: Record<string, string> = {}
  names.forEach((name, index) => {
    palette[name] = cssVar(`--ansi-${index}`, '#888888')
  })
  return {
    background: cssVar('--screen', '#141b1f'),
    foreground: cssVar('--screen-ink', '#d6ded9'),
    cursor: cssVar('--screen-ink', '#d6ded9'),
    cursorAccent: cssVar('--screen', '#141b1f'),
    selectionBackground: 'rgba(134, 183, 232, 0.35)',
    ...palette,
  }
}

function setState(next: typeof state.value, text = '') {
  state.value = next
  message.value = text
  emit('status', next, text)
}

function send(payload: object | Uint8Array) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return
  socket.send(payload instanceof Uint8Array ? payload : JSON.stringify(payload))
}

function connect() {
  if (!terminal) return
  socket?.close()
  setState('connecting')
  terminal.reset()
  const { cols, rows } = terminal
  const url = socketUrl(`/terminal/${encodeURIComponent(props.session)}?mode=${props.mode}&cols=${cols}&rows=${rows}`)
  const current = new WebSocket(url)
  current.binaryType = 'arraybuffer'
  socket = current
  current.onmessage = (event: MessageEvent<ArrayBuffer | string>) => {
    if (socket !== current) return
    if (event.data instanceof ArrayBuffer) {
      terminal?.write(new Uint8Array(event.data))
      return
    }
    let notice: { type: string; message?: string }
    try {
      notice = JSON.parse(event.data)
    } catch {
      return
    }
    if (notice.type === 'ready') {
      setState('ready')
      sendResize()
      if (props.autofocus && props.mode === 'interactive') terminal?.focus()
    } else if (notice.type === 'exit') {
      setState('closed', 'The terminal detached. The session may have ended.')
    } else if (notice.type === 'error') {
      setState('error', notice.message ?? 'The terminal could not attach.')
    }
  }
  current.onclose = () => {
    if (socket !== current) return
    if (state.value === 'ready' || state.value === 'connecting') {
      setState('closed', state.value === 'connecting' ? 'Could not connect to the session.' : 'Disconnected.')
    }
  }
}

function sendResize() {
  if (!terminal) return
  send({ type: 'resize', cols: terminal.cols, rows: terminal.rows })
}

function refit() {
  window.clearTimeout(resizeTimer)
  resizeTimer = window.setTimeout(() => {
    try {
      fit?.fit()
    } catch {
      /* The container is hidden; fit again when it becomes visible. */
    }
  }, 40)
}

onMounted(() => {
  terminal = new Terminal({
    fontFamily: "'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, Menlo, monospace",
    fontSize: prefs.values.terminalFontSize,
    lineHeight: 1.12,
    cursorBlink: props.mode === 'interactive',
    disableStdin: props.mode === 'readonly',
    scrollback: 8000,
    allowProposedApi: true,
    theme: theme(),
  })
  fit = new FitAddon()
  terminal.loadAddon(fit)
  terminal.loadAddon(new WebLinksAddon())
  const unicode = new Unicode11Addon()
  terminal.loadAddon(unicode)
  terminal.unicode.activeVersion = '11'
  terminal.open(container.value!)
  refit()
  terminal.onData((data) => {
    if (props.mode === 'interactive') send({ type: 'input', data })
  })
  terminal.onBinary((data) => {
    if (props.mode === 'interactive') send(Uint8Array.from(data, (character) => character.charCodeAt(0) & 0xff))
  })
  terminal.onResize(() => sendResize())
  observer = new ResizeObserver(() => refit())
  observer.observe(container.value!)
  connect()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  window.clearTimeout(resizeTimer)
  const current = socket
  socket = null
  current?.close()
  terminal?.dispose()
  terminal = null
})

watch(
  () => [props.session, props.mode],
  () => {
    if (terminal) {
      terminal.options.disableStdin = props.mode === 'readonly'
      terminal.options.cursorBlink = props.mode === 'interactive'
      connect()
    }
  },
)

watch(
  () => prefs.values.terminalFontSize,
  (size) => {
    if (terminal) {
      terminal.options.fontSize = size
      refit()
    }
  },
)

defineExpose({
  focus: () => terminal?.focus(),
  reconnect: connect,
  typeText: (text: string) => send({ type: 'input', data: text }),
  sendBytes: (text: string) => send(encoder.encode(text)),
})
</script>

<template>
  <div class="terminal-frame" :class="state">
    <div ref="container" class="terminal-host" :data-session="session" data-testid="terminal" />
    <div v-if="state !== 'ready'" class="overlay" role="status">
      <p>{{ state === 'connecting' ? `Attaching to ${session}…` : message }}</p>
      <button v-if="state !== 'connecting'" type="button" class="again" @click="connect">
        <RefreshCw :size="14" aria-hidden="true" /> Reconnect
      </button>
    </div>
  </div>
</template>

<style scoped>
.terminal-frame {
  position: relative;
  height: 100%;
  min-height: 240px;
  background: var(--screen);
  border-radius: var(--radius);
  padding: 8px 4px 4px 8px;
  overflow: hidden;
}

.terminal-host {
  height: 100%;
  width: 100%;
}

.terminal-host :deep(.xterm) {
  height: 100%;
}

.terminal-host :deep(.xterm-viewport) {
  scrollbar-width: thin;
  scrollbar-color: var(--screen-line) transparent;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: color-mix(in srgb, var(--screen) 82%, transparent);
  color: var(--screen-ink);
  font-size: var(--text-sm);
  text-align: center;
  padding: var(--space-4);
}

.overlay p {
  margin: 0;
  max-width: 48ch;
}

.connecting .overlay {
  background: transparent;
  pointer-events: none;
}

.again {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--screen-line);
  background: var(--screen-2);
  color: var(--screen-ink);
  border-radius: var(--radius);
  padding: 6px 12px;
  cursor: pointer;
}
</style>
