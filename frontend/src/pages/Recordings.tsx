import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Video, Calendar, Download } from 'lucide-react'
import { recordingsApi, camerasApi } from '../api'

function Recordings() {
  const [searchParams] = useSearchParams()
  const initialCameraId = searchParams.get('camera')
  
  const [selectedCamera, setSelectedCamera] = useState<number | null>(
    initialCameraId ? parseInt(initialCameraId) : null
  )
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.getAll,
  })

  const { data: datesData } = useQuery({
    queryKey: ['recordings', 'dates', selectedCamera],
    queryFn: () => recordingsApi.getDates(selectedCamera!),
    enabled: !!selectedCamera,
  })

  const { data: segmentsData } = useQuery({
    queryKey: ['recordings', 'segments', selectedCamera, selectedDate],
    queryFn: () => recordingsApi.getSegments(selectedCamera!, selectedDate || undefined),
    enabled: !!selectedCamera && !!selectedDate,
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Записи</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Camera selection */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium text-gray-900 mb-3">Камеры</h3>
          <div className="space-y-2">
            {cameras?.map((camera) => (
              <button
                key={camera.id}
                onClick={() => {
                  setSelectedCamera(camera.id)
                  setSelectedDate(null)
                }}
                className={`w-full text-left px-3 py-2 rounded ${
                  selectedCamera === camera.id
                    ? 'bg-blue-100 text-blue-800'
                    : 'hover:bg-gray-100'
                }`}
              >
                {camera.name}
              </button>
            ))}
          </div>
        </div>

        {/* Date selection */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-medium text-gray-900 mb-3">Даты</h3>
          {selectedCamera ? (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {datesData?.dates?.length > 0 ? (
                datesData.dates.map((item: { date: string; segment_count: number }) => (
                  <button
                    key={item.date}
                    onClick={() => setSelectedDate(item.date)}
                    className={`w-full text-left px-3 py-2 rounded flex items-center justify-between ${
                      selectedDate === item.date
                        ? 'bg-blue-100 text-blue-800'
                        : 'hover:bg-gray-100'
                    }`}
                  >
                    <span className="flex items-center">
                      <Calendar className="h-4 w-4 mr-2" />
                      {item.date}
                    </span>
                    <span className="text-xs text-gray-500">
                      {item.segment_count} сегм.
                    </span>
                  </button>
                ))
              ) : (
                <p className="text-gray-500 text-sm">Нет записей</p>
              )}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Выберите камеру</p>
          )}
        </div>

        {/* Segments */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-4">
          <h3 className="font-medium text-gray-900 mb-3">Сегменты</h3>
          {selectedDate ? (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {segmentsData?.segments?.length > 0 ? (
                segmentsData.segments.map((segment: { filename: string; path: string; size: number }) => (
                  <div
                    key={segment.filename}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded"
                  >
                    <div className="flex items-center">
                      <Video className="h-5 w-5 text-gray-400 mr-3" />
                      <div>
                        <p className="font-medium text-gray-900">{segment.filename}</p>
                        <p className="text-sm text-gray-500">
                          {(segment.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <a
                      href={`/api/media/${selectedCamera}/${selectedDate}/segments/${segment.filename}`}
                      download
                      className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded"
                    >
                      <Download className="h-5 w-5" />
                    </a>
                  </div>
                ))
              ) : (
                <p className="text-gray-500 text-sm">Нет сегментов</p>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <Video className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-gray-500">Выберите камеру и дату</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Recordings
