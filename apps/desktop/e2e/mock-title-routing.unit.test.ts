import { afterEach, describe, expect, it } from 'vitest'

import { receivedUserTexts, restartMockServer, startMockServer } from './mock-server'

const servers: Array<Awaited<ReturnType<typeof startMockServer>>> = []

afterEach(async () => {
  await Promise.all(servers.splice(0).map(server => server.close()))
})

async function postCompletion(url: string, body: Record<string, unknown>): Promise<string> {
  const response = await fetch(`${url}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body)
  })

  expect(response.ok).toBe(true)
  return response.text()
}

function streamedText(body: string): string {
  return body
    .split('\n')
    .filter(line => line.startsWith('data: ') && line !== 'data: [DONE]')
    .map(line => JSON.parse(line.slice('data: '.length)).choices[0]?.delta?.content ?? '')
    .join('')
}

describe('mock server auxiliary title routing', () => {
  it.each([
    ['E2E_INTERIM_TRIGGER', 'Let me start by planning the approach.'],
    ['E2E_CORRECTION_SWITCH_TRIGGER', 'Checking the long-running task before I continue.'],
    ['E2E_SIDEBAR_CROSS', 'Starting a long background task and delegating work.'],
  ])('el título no consume el primer turno de %s', async (trigger, expectedText) => {
    restartMockServer()
    const server = await startMockServer()
    servers.push(server)
    const triggerText = `${trigger} alpha beta gamma delta epsilon zeta eta theta`

    const titleRequest = {
      model: 'mock-model',
      stream: false,
      messages: [
        { role: 'system', content: 'Name this session.' },
        { role: 'user', content: triggerText }
      ],
      response_format: {
        type: 'json_schema',
        json_schema: {
          name: 'session_title',
          strict: true,
          schema: {
            type: 'object',
            properties: { title: { type: 'string' } },
            required: ['title'],
            additionalProperties: false
          }
        }
      }
    }

    const titleBody = await postCompletion(server.url, titleRequest)
    expect(JSON.parse(JSON.parse(titleBody).choices[0].message.content)).toEqual({
      title: `${trigger} alpha beta gamma delta epsilon zeta`
    })

    const chatBody = await postCompletion(server.url, {
      model: 'mock-model',
      stream: true,
      messages: [{ role: 'user', content: triggerText }]
    })

    expect(streamedText(chatBody)).toBe(expectedText)
    expect(server.receivedPrompts).toEqual([triggerText])
    expect(receivedUserTexts()).toEqual([triggerText])
  })
})
