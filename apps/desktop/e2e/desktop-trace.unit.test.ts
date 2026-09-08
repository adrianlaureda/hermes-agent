import { describe, expect, it } from 'vitest'
import { closeTracedDesktop, initializeTracedDesktop, startDesktopTrace } from './desktop-trace'

function fixture(failStop = false) {
  const events: string[] = []
  const app = {
    context: () => ({ tracing: {
      start: async () => { events.push('start') },
      stop: async ({ path }: { path: string }) => {
        events.push(`stop:${path}`)
        if (failStop) throw new Error('trace failure')
      },
    } }),
    close: async () => { events.push('close') },
  }
  const output = { path: '/synthetic/trace.zip', attach: async () => { events.push('attach') } }
  return { app, output, events }
}

describe('trazas de Electron con API pública', () => {
  it('cierra si falla el inicio de la captura', async () => {
    const { app, output, events } = fixture()
    app.context = () => ({ tracing: {
      start: async () => { throw new Error('start failure') },
      stop: async () => { events.push('unexpected stop') },
    } })
    await expect(initializeTracedDesktop(app, output, async () => {})).rejects.toThrow('start failure')
    expect(events).toEqual(['close'])
  })
  it('guarda la captura y cierra si falla firstWindow', async () => {
    const { app, output, events } = fixture()
    await expect(initializeTracedDesktop(app, output, async () => { throw new Error('window failure') })).rejects.toThrow('window failure')
    expect(events).toEqual(['start', 'stop:/synthetic/trace.zip', 'attach', 'close'])
  })
  it('conserva ambos errores si fallan la captura y el cierre', async () => {
    const { app, output } = fixture(true)
    app.close = async () => { throw new Error('close failure') }
    await startDesktopTrace(app, output)
    try {
      await closeTracedDesktop(app)
      expect.fail('Debe fallar')
    } catch (error) {
      expect(error).toBeInstanceOf(AggregateError)
      expect((error as AggregateError).errors.map(error => error.message)).toEqual(['trace failure', 'close failure'])
    }
  })
  it('guarda y adjunta la traza antes de cerrar el contexto', async () => {
    const { app, output, events } = fixture()
    await startDesktopTrace(app, output)
    await closeTracedDesktop(app)
    expect(events).toEqual(['start', 'stop:/synthetic/trace.zip', 'attach', 'close'])
  })
  it('cierra Electron aunque falle la traza y conserva el error', async () => {
    const { app, output, events } = fixture(true)
    await startDesktopTrace(app, output)
    await expect(closeTracedDesktop(app)).rejects.toThrow('trace failure')
    expect(events).toEqual(['start', 'stop:/synthetic/trace.zip', 'close'])
  })
  it('cierra una app sin captura registrada', async () => {
    const { app, events } = fixture()
    await closeTracedDesktop(app)
    expect(events).toEqual(['close'])
  })
})
