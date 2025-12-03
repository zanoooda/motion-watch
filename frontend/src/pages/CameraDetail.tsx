import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { ArrowLeft, Save } from 'lucide-react'
import { camerasApi, Camera } from '../api'

function CameraDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const cameraId = parseInt(id || '0')

  const { data: camera, isLoading } = useQuery({
    queryKey: ['cameras', cameraId],
    queryFn: () => camerasApi.getById(cameraId),
    enabled: cameraId > 0,
  })

  const [formData, setFormData] = useState<Partial<Camera>>({})

  useEffect(() => {
    if (camera) {
      setFormData(camera)
    }
  }, [camera])

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Camera>) => camerasApi.update(cameraId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      navigate('/cameras')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const { id: _id, status, created_at, updated_at, last_seen, ...updateData } = formData as Camera
    updateMutation.mutate(updateData)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!camera) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Камера не найдена</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center mb-6">
        <button
          onClick={() => navigate('/cameras')}
          className="mr-4 p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <h1 className="text-2xl font-bold text-gray-900">
          Настройки камеры: {camera.name}
        </h1>
      </div>

      <div className="bg-white rounded-lg shadow">
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Название
              </label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                URL потока
              </label>
              <input
                type="text"
                value={formData.url || ''}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>
          </div>

          <div className="border-t pt-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Настройки записи</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.is_enabled || false}
                  onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Камера включена</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.recording_enabled || false}
                  onChange={(e) => setFormData({ ...formData, recording_enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Запись видео</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.audio_enabled || false}
                  onChange={(e) => setFormData({ ...formData, audio_enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Запись аудио</span>
              </label>
            </div>
          </div>

          <div className="border-t pt-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Детекция движения</h3>
            <div className="space-y-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.motion_detection_enabled || false}
                  onChange={(e) => setFormData({ ...formData, motion_detection_enabled: e.target.checked })}
                  className="h-4 w-4 text-blue-600 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">Включить детекцию движения</span>
              </label>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Чувствительность: {formData.motion_sensitivity || 25}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={formData.motion_sensitivity || 25}
                  onChange={(e) => setFormData({ ...formData, motion_sensitivity: parseInt(e.target.value) })}
                  className="w-full"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Выше значение = более чувствительная детекция
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Минимальная область (пиксели)
                  </label>
                  <input
                    type="number"
                    value={formData.motion_min_area || 500}
                    onChange={(e) => setFormData({ ...formData, motion_min_area: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    min="0"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Минимальный размер области движения для срабатывания
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cooldown (секунды)
                  </label>
                  <input
                    type="number"
                    value={formData.motion_cooldown || 30}
                    onChange={(e) => setFormData({ ...formData, motion_cooldown: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                    min="0"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Минимальный интервал между уведомлениями
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-6 border-t">
            <button
              type="button"
              onClick={() => navigate('/cameras')}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 mr-3"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={updateMutation.isPending}
              className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Save className="h-5 w-5 mr-2" />
              {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CameraDetail
