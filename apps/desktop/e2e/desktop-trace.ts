/** Traza por sesión Electron: se guarda antes de cerrar el contexto. */
interface TraceableDesktop {
  context(): { tracing: {
    start(options: { screenshots: boolean; snapshots: boolean; sources: boolean }): Promise<void>
    stop(options: { path: string }): Promise<void>
  } }
  close(): Promise<void>
}
interface TraceOutput {
  path: string
  attach(): Promise<void>
}
const captures = new WeakMap<TraceableDesktop, TraceOutput>()

export async function startDesktopTrace(app: TraceableDesktop, output: TraceOutput): Promise<void> {
  await app.context().tracing.start({ screenshots: true, snapshots: true, sources: true })
  captures.set(app, output)
}

export async function closeTracedDesktop(app: TraceableDesktop): Promise<void> {
  const output = captures.get(app)
  captures.delete(app)
  try {
    if (output) {
      await app.context().tracing.stop({ path: output.path })
      await output.attach()
    }
  } finally {
    // Un fallo de captura nunca debe dejar Electron abierto.
    await app.close()
  }
}
