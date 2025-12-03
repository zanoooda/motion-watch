import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { 
  Video, 
  Calendar, 
  Clock, 
  Camera,
  Download,
  Play,
  FolderOpen
} from 'lucide-react'
import { camerasApi, recordingsApi, Recording } from '../api'
import { format } from 'date-fns'

function Recordings() {
  const [searchParams] = useSearchParams()
  const initialCamera = searchParams.get('camera')
  const [cameraFilter, setCameraFilter] = useState<number | null>(
    initialCamera ? parseInt(initialCamera) : null
  )
  const [dateFilter, setDateFilter] = useState<string>('')
  const [page, setPage] = useState(1)
  const limit = 24

  const { data: recordings, isLoading: recordingsLoading } = useQuery({
    queryKey: ['recordings', cameraFilter, dateFilter, page],
    queryFn: () => recordingsApi.getAll({ 
      camera_id: cameraFilter || undefined,
      date: dateFilter || undefined,
      limit,
      offset: (page - 1) * limit
    }),
  })

  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: camerasApi.getAll,
  })

  if (recordingsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  // Group recordings by date
  const recordingsByDate = recordings?.reduce((acc, recording) => {
    const date = format(new Date(recording.start_time), 'yyyy-MM-dd')
    if (!acc[date]) {
      acc[date] = []
    }
    acc[date].push(recording)
    return acc
  }, {} as Record<string, Recording[]>) || {}

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Recordings</h1>
        
        {/* Filters */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center">
            <Camera className="h-5 w-5 text-gray-400 mr-2" />
            <select
              value={cameraFilter || ''}
              onChange={(e) => {
                setCameraFilter(e.target.value ? parseInt(e.target.value) : null)
                setPage(1)
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All cameras</option>
              {cameras?.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center">
            <Calendar className="h-5 w-5 text-gray-400 mr-2" />
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => {
                setDateFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {recordings && recordings.length > 0 ? (
        <>
          {/* Recordings by date */}
          {Object.entries(recordingsByDate)
            .sort(([a], [b]) => b.localeCompare(a))
            .map(([date, dateRecordings]) => (
              <div key={date} className="mb-8">
                <h2 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
                  <Calendar className="h-5 w-5 mr-2" />
                  {format(new Date(date), 'EEEE, MMMM d, yyyy')}
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                  {dateRecordings.map((recording) => (
                    <RecordingCard 
                      key={recording.id} 
                      recording={recording} 
                      cameras={cameras || []} 
                    />
                  ))}
                </div>
              </div>
            ))}

          {/* Pagination */}
          <div className="mt-6 flex items-center justify-center space-x-4">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-gray-600">Page {page}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={recordings.length < limit}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </>
      ) : (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <FolderOpen className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-lg font-medium text-gray-900">No recordings</h3>
          <p className="mt-1 text-gray-500">
            Recordings will appear here when cameras are recording
          </p>
        </div>
      )}
    </div>
  )
}

// Recording Card Component
function RecordingCard({ recording, cameras }: { recording: Recording; cameras: any[] }) {
  const camera = cameras.find(c => c.id === recording.camera_id)
  const duration = Math.round(recording.duration || 0)
  const minutes = Math.floor(duration / 60)
  const seconds = duration % 60

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition-shadow group">
      {/* Thumbnail */}
      <div className="aspect-video bg-gray-800 relative flex items-center justify-center">
        <Video className="h-8 w-8 text-gray-500" />
        
        {/* Play overlay */}
        <a
          href={`/api/recordings/${recording.id}/video`}
          target="_blank"
          rel="noopener noreferrer"
          className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <div className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center">
            <Play className="h-6 w-6 text-gray-800 ml-1" />
          </div>
        </a>

        {/* Duration badge */}
        <div className="absolute bottom-2 right-2">
          <span className="px-2 py-1 bg-black/60 text-white text-xs rounded">
            {minutes}:{seconds.toString().padStart(2, '0')}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="p-3">
        <div className="flex items-center text-gray-600 text-xs mb-1">
          <Camera className="h-3 w-3 mr-1" />
          <span className="truncate">{camera?.name || 'Unknown'}</span>
        </div>
        <div className="flex items-center text-gray-500 text-xs">
          <Clock className="h-3 w-3 mr-1" />
          {format(new Date(recording.start_time), 'HH:mm:ss')}
        </div>
        
        {/* Download button */}
        <a
          href={`/api/recordings/${recording.id}/download`}
          className="mt-2 flex items-center justify-center w-full py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
        >
          <Download className="h-3 w-3 mr-1" />
          Download
        </a>
      </div>
    </div>
  )
}

export default Recordings
