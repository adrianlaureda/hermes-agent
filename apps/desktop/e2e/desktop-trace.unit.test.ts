import { describe, expect, it } from 'vitest'
import { closeTracedDesktop, startDesktopTrace } from './desktop-trace'

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
