import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Settings as SettingsIcon, 
  Bell,
  Save,
  HardDrive,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { settingsApi, Settings as SettingsType } from '../api'

function Settings() {
  const queryClient = useQueryClient()
  const [settings, setSettings] = useState<Partial<SettingsType>>({})
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')

  const { data: currentSettings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.getAll,
  })

  const updateMutation = useMutation({
    mutationFn: settingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })

  const cleanupMutation = useMutation({
    mutationFn: settingsApi.cleanupStorage,
  })

  useEffect(() => {
    if (currentSettings) {
      setSettings(currentSettings)
    }
  }, [currentSettings])

  const handleSave = () => {
    updateMutation.mutate(settings)
  }

  const handleTestTelegram = async () => {
    setTestStatus('testing')
    try {
      await settingsApi.testTelegram()
      setTestStatus('success')
      setTimeout(() => setTestStatus('idle'), 3000)
    } catch {
      setTestStatus('error')
      setTimeout(() => setTestStatus('idle'), 3000)
    }
  }

  const handleCleanup = () => {
    if (confirm('Are you sure you want to clean up old recordings? This cannot be undone.')) {
      cleanupMutation.mutate()
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="h-5 w-5 mr-2" />
          {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      <div className="space-y-6">
        {/* Telegram Settings */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Bell className="h-5 w-5 mr-2" />
            Telegram Notifications
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Bot Token
              </label>
              <input
                type="password"
                value={settings.telegram_bot_token || ''}
                onChange={(e) => setSettings({ ...settings, telegram_bot_token: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
              />
              <p className="text-xs text-gray-500 mt-1">
                Get your bot token from @BotFather on Telegram
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Chat ID
              </label>
              <input
                type="text"
                value={settings.telegram_chat_id || ''}
                onChange={(e) => setSettings({ ...settings, telegram_chat_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                placeholder="-1001234567890"
              />
              <p className="text-xs text-gray-500 mt-1">
                Your personal chat ID or group chat ID where notifications will be sent
              </p>
            </div>

            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.telegram_enabled || false}
                  onChange={(e) => setSettings({ ...settings, telegram_enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Enable Telegram notifications</span>
              </label>
            </div>

            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.telegram_send_snapshots || false}
                  onChange={(e) => setSettings({ ...settings, telegram_send_snapshots: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Send motion snapshots to Telegram</span>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default notification cooldown (seconds)
              </label>
              <input
                type="number"
                value={settings.notification_cooldown || 60}
                onChange={(e) => setSettings({ ...settings, notification_cooldown: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                min="0"
              />
              <p className="text-xs text-gray-500 mt-1">
                Minimum time between notifications (per camera). Can be overridden per camera.
              </p>
            </div>

            <button
              onClick={handleTestTelegram}
              disabled={testStatus === 'testing'}
              className="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              {testStatus === 'testing' ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Testing...
                </>
              ) : testStatus === 'success' ? (
                <>
                  <CheckCircle className="h-4 w-4 mr-2 text-green-600" />
                  Test successful!
                </>
              ) : testStatus === 'error' ? (
                <>
                  <XCircle className="h-4 w-4 mr-2 text-red-600" />
                  Test failed
                </>
              ) : (
                <>
                  <Bell className="h-4 w-4 mr-2" />
                  Send test notification
                </>
              )}
            </button>
          </div>
        </div>

        {/* Storage Settings */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <HardDrive className="h-5 w-5 mr-2" />
            Storage Management
          </h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Recording retention (days)
              </label>
              <input
                type="number"
                value={settings.retention_days || 7}
                onChange={(e) => setSettings({ ...settings, retention_days: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                min="1"
              />
              <p className="text-xs text-gray-500 mt-1">
                Recordings older than this will be automatically deleted
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Events retention (days)
              </label>
              <input
                type="number"
                value={settings.events_retention_days || 30}
                onChange={(e) => setSettings({ ...settings, events_retention_days: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                min="1"
              />
              <p className="text-xs text-gray-500 mt-1">
                Motion events older than this will be automatically deleted
              </p>
            </div>

            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.auto_cleanup || false}
                  onChange={(e) => setSettings({ ...settings, auto_cleanup: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Enable automatic cleanup</span>
              </label>
            </div>

            <div className="pt-4 border-t">
              <button
                onClick={handleCleanup}
                disabled={cleanupMutation.isPending}
                className="inline-flex items-center px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                {cleanupMutation.isPending ? 'Cleaning up...' : 'Clean up old recordings now'}
              </button>
              {cleanupMutation.isSuccess && (
                <p className="text-sm text-green-600 mt-2">Cleanup completed successfully</p>
              )}
            </div>
          </div>
        </div>

        {/* Detection Defaults */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <SettingsIcon className="h-5 w-5 mr-2" />
            Default Detection Settings
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            These settings will be used as defaults for new cameras
          </p>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default sensitivity: {settings.default_sensitivity || 25}%
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={settings.default_sensitivity || 25}
                onChange={(e) => setSettings({ ...settings, default_sensitivity: parseInt(e.target.value) })}
                className="w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default motion cooldown (seconds)
              </label>
              <input
                type="number"
                value={settings.default_motion_cooldown || 30}
                onChange={(e) => setSettings({ ...settings, default_motion_cooldown: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                min="0"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Default video clip duration (seconds)
              </label>
              <input
                type="number"
                value={settings.default_clip_duration || 10}
                onChange={(e) => setSettings({ ...settings, default_clip_duration: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                min="5"
                max="120"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings
