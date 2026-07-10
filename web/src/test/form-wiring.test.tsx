import { zodResolver } from '@hookform/resolvers/zod'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useForm } from 'react-hook-form'
import { describe, expect, it } from 'vitest'
import { z } from 'zod'

// Proves the react-hook-form + zod + @hookform/resolvers wiring works
// (ADR-0006); the first real form lands with guided sheet entry (Phase 2).
const schema = z.object({
  callsign: z.string().min(1, 'Callsign is required'),
})

function TestForm() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema) })

  return (
    <form onSubmit={handleSubmit(() => {})}>
      <input {...register('callsign')} aria-label="Callsign" />
      {errors.callsign && <span role="alert">{errors.callsign.message}</span>}
      <button type="submit">Submit</button>
    </form>
  )
}

describe('react-hook-form + zod wiring', () => {
  it('surfaces zod validation errors through the resolver', async () => {
    const user = userEvent.setup()
    render(<TestForm />)

    await user.click(screen.getByRole('button', { name: 'Submit' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Callsign is required')
  })
})
