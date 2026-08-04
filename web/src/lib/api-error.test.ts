import { describe, expect, it } from 'vitest'

import { apiErrorMessage } from './api-error'

describe('apiErrorMessage', () => {
  it('prefers the server detail', () => {
    expect(apiErrorMessage({ detail: 'uploaded file exceeds 25MB size limit' }, 'fallback')).toBe(
      'uploaded file exceeds 25MB size limit',
    )
  })

  it('falls back for an unknown error shape', () => {
    expect(apiErrorMessage({ status: 503 }, 'LLM unavailable')).toBe('LLM unavailable')
  })
})
