'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://corben.pro'

export default function MicrosoftIntegration() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'connecting' | 'success' | 'error'>('loading')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const errorParam = searchParams.get('error')

    if (errorParam) {
      setStatus('error')
      setError(searchParams.get('error_description') || 'Authorization was cancelled or denied')
      return
    }

    if (code) {
      handleCallback(code, state)
    } else {
      startOAuthFlow()
    }
  }, [searchParams])

  const startOAuthFlow = async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      router.push('/')
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/integrations/outlook/auth`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error('Failed to get authorization URL')
      }

      const data = await response.json()
      localStorage.setItem('oauth_state', data.state)
      window.location.href = data.authorization_url
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Failed to start authorization')
    }
  }

  const handleCallback = async (code: string, state: string | null) => {
    setStatus('connecting')

    const token = localStorage.getItem('token')
    const savedState = localStorage.getItem('oauth_state')

    if (!token) {
      router.push('/')
      return
    }

    if (state && savedState && state !== savedState) {
      setStatus('error')
      setError('Invalid OAuth state. Please try again.')
      return
    }

    try {
      const response = await fetch(`${API_URL}/api/integrations/outlook/callback`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code, state }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to connect Outlook')
      }

      localStorage.removeItem('oauth_state')
      setStatus('success')

      setTimeout(() => {
        router.push('/dashboard')
      }, 2000)
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Failed to connect')
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8 text-center">
        <div className="mb-6">
          <svg className="w-16 h-16 mx-auto" viewBox="0 0 24 24">
            <path fill="#0078D4" d="M23.5 12c0 6.351-5.149 11.5-11.5 11.5S.5 18.351.5 12 5.649.5 12 .5 23.5 5.649 23.5 12z"/>
            <path fill="#fff" d="M12 5.5c-3.584 0-6.5 2.916-6.5 6.5s2.916 6.5 6.5 6.5 6.5-2.916 6.5-6.5-2.916-6.5-6.5-6.5zm0 11c-2.481 0-4.5-2.019-4.5-4.5s2.019-4.5 4.5-4.5 4.5 2.019 4.5 4.5-2.019 4.5-4.5 4.5z"/>
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Microsoft Outlook
        </h1>

        {status === 'loading' && (
          <div>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Redirecting to Microsoft...</p>
          </div>
        )}

        {status === 'connecting' && (
          <div>
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Connecting your Outlook calendar...</p>
          </div>
        )}

        {status === 'success' && (
          <div>
            <div className="text-green-500 text-5xl mb-4">&#10003;</div>
            <p className="text-green-600 font-medium">Successfully connected!</p>
            <p className="text-gray-500 text-sm mt-2">Redirecting to dashboard...</p>
          </div>
        )}

        {status === 'error' && (
          <div>
            <div className="text-red-500 text-5xl mb-4">&#10005;</div>
            <p className="text-red-600 font-medium mb-4">{error}</p>
            <button
              onClick={() => {
                setStatus('loading')
                setError(null)
                startOAuthFlow()
              }}
              className="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 transition"
            >
              Try Again
            </button>
            <button
              onClick={() => router.push('/dashboard')}
              className="block mx-auto mt-4 text-gray-500 hover:text-gray-700 text-sm"
            >
              Back to Dashboard
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
