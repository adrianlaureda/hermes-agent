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
  const errors: unknown[] = []
  try {
    if (output) {
      await app.context().tracing.stop({ path: output.path })
      await output.attach()
    }
  } catch (error) {
    errors.push(error)
  }
  // Un fallo de captura nunca debe dejar Electron abierto.
  try {
    await app.close()
  } catch (error) {
    errors.push(error)
  }
  if (errors.length === 1) throw errors[0]
  if (errors.length > 1) throw new AggregateError(errors, 'Fallaron la captura y el cierre de Electron')
}

export async function initializeTracedDesktop<T>(
  app: TraceableDesktop,
  output: TraceOutput,
  initialize: () => Promise<T>,
): Promise<T> {
  try {
    await startDesktopTrace(app, output)
    return await initialize()
  } catch (error) {
    try {
      await closeTracedDesktop(app)
    } catch (cleanupError) {
      throw new AggregateError([error, cleanupError], 'Fallaron el arranque y la limpieza de Electron')
    }
    throw error
  }
}
