import { describe, expect, it } from 'vitest'

import config from '../playwright.config'

describe('configuración Playwright de escritorio', () => {
  it('serializa los stacks reales de Electron', () => {
    expect(config.workers).toBe(1)
    expect(config.fullyParallel).toBe(false)
  })
})
