/**
 * Build a disposable Alfred workspace (real Git repositories with a bare remote), isolate tmux on
 * a private socket, and start alfred-ui against it. Tests read the details from environment
 * variables; the returned function stops the server, the private tmux server, and removes files.
 */
import { execFileSync, spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const UI = fileURLToPath(new URL('../..', import.meta.url)).replace(/\/$/, '')
const TOKEN = 'e2e-access-token'

export default async function globalSetup(): Promise<() => Promise<void>> {
  const root = mkdtempSync(join(tmpdir(), 'aui-e2e-'))
  const tmux = mkdtempSync(join(tmpdir(), 'auit-'))
  const workspace = join(root, 'workspace')
  const prefix = `aui-e2e-${process.pid}`
  const python = join(UI, '.venv', 'bin', 'python')
  execFileSync(python, [join(UI, 'scripts', 'make_sandbox.py'), '--root', workspace, '--prefix', prefix, '--second-repo'], {
    stdio: 'inherit',
  })
  const config = join(workspace, '.alfred', 'config.toml')
  const environment: NodeJS.ProcessEnv = { ...process.env, TMUX_TMPDIR: tmux }
  delete environment.TMUX

  const server = spawn(join(UI, '.venv', 'bin', 'alfred-ui'), ['--config', config, '--port', '0', '--token', TOKEN], {
    env: environment,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  const port = await new Promise<number>((done, fail) => {
    let output = ''
    const timer = setTimeout(() => fail(new Error(`alfred-ui did not start:\n${output}`)), 20_000)
    const read = (chunk: Buffer) => {
      output += chunk.toString()
      const match = /Open http:\/\/127\.0\.0\.1:(\d+)\//.exec(output)
      if (match) {
        clearTimeout(timer)
        done(Number(match[1]))
      }
    }
    server.stdout?.on('data', read)
    server.stderr?.on('data', read)
    server.on('exit', (code) => fail(new Error(`alfred-ui exited with ${code}:\n${output}`)))
  })

  Object.assign(process.env, {
    AUI_BASE: `http://127.0.0.1:${port}`,
    AUI_TOKEN: TOKEN,
    AUI_ROOT: root,
    AUI_WORKSPACE: workspace,
    AUI_CONFIG: config,
    AUI_TMUX: tmux,
    AUI_PREFIX: prefix,
    AUI_UI: UI,
  })

  return async () => {
    server.kill('SIGTERM')
    try {
      execFileSync('tmux', ['kill-server'], { env: environment, stdio: 'ignore' })
    } catch {
      /* No tmux server was started. */
    }
    if (!process.env.AUI_KEEP) {
      rmSync(root, { recursive: true, force: true })
      rmSync(tmux, { recursive: true, force: true })
    } else {
      console.log(`Kept ${root}`)
    }
  }
}
