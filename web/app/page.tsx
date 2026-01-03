'use client'

import { useEffect, useState } from 'react'

declare global {
  interface Window {
    TelegramLoginWidget: {
      dataOnauth: (user: TelegramUser) => void
    }
  }
}

interface TelegramUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

export default function Home() {
  const [user, setUser] = useState<TelegramUser | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || 'your_bot'
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''

  useEffect(() => {
    // Set up Telegram auth callback
    window.TelegramLoginWidget = {
      dataOnauth: handleTelegramAuth
    }

    // Load Telegram widget script
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botUsername)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-onauth', 'TelegramLoginWidget.dataOnauth(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true

    const container = document.getElementById('telegram-login')
    if (container) {
      container.appendChild(script)
    }

    return () => {
      if (container && script.parentNode) {
        container.removeChild(script)
      }
    }
  }, [botUsername])

  const handleTelegramAuth = async (telegramUser: TelegramUser) => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${apiUrl}/auth/telegram`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(telegramUser),
      })

      if (!response.ok) {
        throw new Error('Authentication failed')
      }

      const data = await response.json()

      // Store token
      localStorage.setItem('token', data.access_token)
      setUser(telegramUser)

      // Redirect to dashboard
      window.location.href = '/dashboard'
    } catch (err) {
      setError('Ошибка авторизации. Попробуйте ещё раз.')
      console.error('Auth error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            📅 AI Calendar Assistant
          </h1>
          <p className="text-gray-600">
            Управляйте календарём через Telegram
          </p>
        </div>

        <div className="space-y-6">
          <div className="bg-blue-50 rounded-lg p-4">
            <h2 className="font-semibold text-blue-900 mb-2">Что умеет бот:</h2>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✓ Создаёт события из текстовых сообщений</li>
              <li>✓ Распознаёт голосовые сообщения</li>
              <li>✓ Обрабатывает пересланные сообщения</li>
              <li>✓ Интегрируется с Google, Outlook, Apple</li>
            </ul>
          </div>

          {error && (
            <div className="bg-red-50 text-red-700 rounded-lg p-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-center">
            {loading ? (
              <div className="text-gray-500">Авторизация...</div>
            ) : user ? (
              <div className="text-green-600">
                ✓ Авторизован как {user.first_name}
              </div>
            ) : (
              <div id="telegram-login" />
            )}
          </div>

          <p className="text-xs text-gray-500 text-center">
            Войдите через Telegram для подключения календарей
          </p>
        </div>
      </div>
    </main>
  )
}
