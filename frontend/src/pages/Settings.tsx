import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Settings as SettingsIcon, HardDrive, Trash2, Bell } from 'lucide-react'
import { settingsApi } from '../api'

function Settings() {
  const [retentionDays, setRetentionDays] = useState(30)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })

  const { data: storageInfo } = useQuery({
    queryKey: ['settings', 'storage'],
    queryFn: settingsApi.getStorage,
  })

  const cleanupMutation = useMutation({
    mutationFn: (days: number) => settingsApi.cleanup(days),
  })

  const handleCleanup = () => {
    if (confirm(`Удалить записи старше ${retentionDays} дней?`)) {
      cleanupMutation.mutate(retentionDays)
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
      <div className="flex items-center mb-6">
        <SettingsIcon className="h-8 w-8 text-gray-400 mr-3" />
        <h1 className="text-2xl font-bold text-gray-900">Настройки</h1>
      </div>

      <div className="space-y-6">
        {/* Telegram Settings */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center">
              <Bell className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900">Telegram уведомления</h2>
            </div>
          </div>
          <div className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">Статус</p>
                <p className="text-sm text-gray-500">
                  {settings?.telegram_configured
                    ? 'Telegram бот настроен и готов к отправке уведомлений'
                    : 'Telegram бот не настроен. Добавьте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env'}
                </p>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-sm ${
                  settings?.telegram_configured
                    ? 'bg-green-100 text-green-800'
                    : 'bg-yellow-100 text-yellow-800'
                }`}
              >
                {settings?.telegram_configured ? 'Активен' : 'Не настроен'}
              </span>
            </div>
          </div>
        </div>

        {/* Storage Settings */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center">
              <HardDrive className="h-5 w-5 text-gray-400 mr-2" />
              <h2 className="text-lg font-medium text-gray-900">Хранилище</h2>
            </div>
          </div>
          <div className="p-6 space-y-6">
            {/* Storage Stats */}
            {storageInfo && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Всего</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {storageInfo.total_gb} ГБ
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Использовано</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {storageInfo.used_gb} ГБ
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Свободно</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {storageInfo.free_gb} ГБ
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Записи</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {storageInfo.recordings_used_gb} ГБ
                  </p>
                </div>
              </div>
            )}

            {/* Storage by camera */}
            {storageInfo?.cameras && storageInfo.cameras.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">По камерам</h3>
                <div className="space-y-2">
                  {storageInfo.cameras.map((cam: { camera_dir: string; size_gb: number }) => (
                    <div
                      key={cam.camera_dir}
                      className="flex items-center justify-between py-2 border-b border-gray-100"
                    >
                      <span className="text-gray-900">{cam.camera_dir}</span>
                      <span className="text-gray-500">{cam.size_gb} ГБ</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Cleanup */}
            <div className="border-t pt-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Очистка старых записей</h3>
              <div className="flex items-end gap-4">
                <div>
                  <label className="block text-sm text-gray-500 mb-1">
                    Удалить записи старше (дней)
                  </label>
                  <input
                    type="number"
                    value={retentionDays}
                    onChange={(e) => setRetentionDays(parseInt(e.target.value))}
                    className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    min="1"
                  />
                </div>
                <button
                  onClick={handleCleanup}
                  disabled={cleanupMutation.isPending}
                  className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                >
                  <Trash2 className="h-5 w-5 mr-2" />
                  {cleanupMutation.isPending ? 'Очистка...' : 'Очистить'}
                </button>
              </div>
              {cleanupMutation.isSuccess && cleanupMutation.data && (
                <p className="mt-2 text-sm text-green-600">
                  Удалено файлов: {cleanupMutation.data.deleted_files}, освобождено: {cleanupMutation.data.freed_gb} ГБ
                </p>
              )}
            </div>
          </div>
        </div>

        {/* System Info */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Система</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Всего камер</p>
                <p className="text-lg font-medium text-gray-900">{settings?.total_cameras || 0}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Активных камер</p>
                <p className="text-lg font-medium text-gray-900">{settings?.active_cameras || 0}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings
