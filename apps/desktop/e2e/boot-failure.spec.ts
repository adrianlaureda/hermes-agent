/**
 * E2E boot-failure tests — verify the app shows an error overlay when the
 * backend can't start.
 *
 * Injects a fake boot error (HERMES_DESKTOP_BOOT_FAKE_ERROR) so the backend
 * resolution fails with a controlled error message. The app should show the
 * BootFailureOverlay with retry/repair actions.
 *
 * Prerequisite: `npm run build` must have been run so dist/ exists.
 */

import { allowErrorBanners, test } from './test'

import {
  type DeadBackendFixture,
  setupDeadBackend,
  waitForBootFailure,
} from './fixtures'
import { expectVisualSnapshot } from './visual-snapshot'

let fixture: DeadBackendFixture | null = null

test.afterAll(async () => {
  if (fixture) {
    fixture.app.on('close', () => console.log('[quit-probe] app-close'))
    fixture.app.context().on('close', () => console.log('[quit-probe] context-close'))
    const child = fixture.app.process()
    child.once('exit', (code, signal) => console.log('[quit-probe] process-exit', code, signal))
    child.stderr?.on('data', (data: Buffer) => {
      for (const line of data.toString().split('\n')) {
        if (line.includes('[quit-probe]')) console.log(line)
      }
    })
    console.log('[quit-probe] before-inspection')
    await fixture.app.evaluate(({ app, BrowserWindow }) => {
      const emit = (event: string, extra: unknown = null) => process.stderr.write(
        '[quit-probe] ' + JSON.stringify({ event, extra, windows: BrowserWindow.getAllWindows().length }) + '\n',
      )
      app.on('before-quit', event => emit('before-quit', event.defaultPrevented))
      app.on('will-quit', event => emit('will-quit', event.defaultPrevented))
      app.on('quit', () => emit('quit'))
      for (const window of BrowserWindow.getAllWindows()) {
        window.on('close', event => emit('window-close', event.defaultPrevented))
        window.on('closed', () => emit('window-closed'))
      }
      emit('ready')
    })
    console.log('[quit-probe] before-cleanup')
  }
  if (fixture) {
    await fixture.app.close()
    console.log('[quit-probe] close-resolved')
    fixture.sandbox.cleanup()
    console.log('[quit-probe] sandbox-removed')
  }
  fixture = null
})

test.describe('boot failure with dead backend', () => {
  test.beforeEach(() => {
    // These tests deliberately trigger boot errors — error banners
    // (notifyError → [role="alert"]) are expected, not failures.
    allowErrorBanners()
  })

  test('app shows error state', async () => {
    // Inject a fake boot error so the backend resolution "fails" with a
    // controlled error message. This is the only reliable way to trigger
    // BootFailureOverlay in dev mode.
    fixture = await setupDeadBackend({ fakeError: true })

    await waitForBootFailure(fixture.page, 90_000)
  })

  test('screenshot of error state', async () => {
    if (!fixture) {
      test.skip(true, 'Previous test failed — no app running')

      return
    }

    await expectVisualSnapshot(fixture!.page, { name: 'boot-failure-error-state', app: fixture.app })
  })
})
