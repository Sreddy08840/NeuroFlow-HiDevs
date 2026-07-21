'use client'

import { useState, useEffect } from 'react'
import { Upload, FileText, CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import api from '@/utils/api'
import type { Document } from '@/types'

export default function DocumentsPage() {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set())
  const queryClient = useQueryClient()

  const { data: documents, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: async () => {
      const res = await api.get('/documents')
      return res.data as Document[]
    },
  })

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    await handleFiles(files)
  }

  const handleFiles = async (files: File[]) => {
    for (const file of files) {
      const fileId = `${file.name}-${Date.now()}`
      setUploadingFiles(prev => new Set(prev).add(fileId))

      try {
        const formData = new FormData()
        formData.append('file', file)
        await api.post('/ingest', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        queryClient.invalidateQueries({ queryKey: ['documents'] })
      } catch (error) {
        console.error('Upload failed:', error)
      } finally {
        setUploadingFiles(prev => {
          const newSet = new Set(prev)
          newSet.delete(fileId)
          return newSet
        })
      }
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'queued':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
      case 'processing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      default:
        return null
    }
  }

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'queued':
      case 'processing':
        return 'bg-blue-50 text-blue-700'
      case 'completed':
        return 'bg-green-50 text-green-700'
      case 'failed':
        return 'bg-red-50 text-red-700'
      default:
        return 'bg-gray-50 text-gray-700'
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-slate-900 mb-8">Documents</h1>

      {/* Upload Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input')?.click()}
        className={`mb-8 p-12 border-2 border-dashed rounded-xl text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-slate-300 hover:border-blue-400 hover:bg-slate-50'
        }`}
      >
        <input
          id="file-input"
          type="file"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(Array.from(e.target.files))}
        />
        <Upload className="w-12 h-12 mx-auto mb-4 text-slate-400" />
        <p className="text-lg font-medium text-slate-700 mb-2">
          Drag and drop files here, or click to select
        </p>
        <p className="text-sm text-slate-500">
          Supported formats: PDF, DOCX, PNG, JPG, CSV
        </p>
      </div>

      {/* Uploading indicator */}
      {uploadingFiles.size > 0 && (
        <div className="mb-6 flex items-center gap-2 text-blue-600">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Uploading {uploadingFiles.size} file(s)...</span>
        </div>
      )}

      {/* Documents List */}
      <div className="grid gap-4">
        {!documents || documents.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 mx-auto mb-4 text-slate-300" />
            <p className="text-slate-500">No documents uploaded yet</p>
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.document_id}
              className="flex items-center justify-between p-4 bg-white rounded-xl shadow-sm border border-slate-200"
            >
              <div className="flex items-center gap-4">
                <FileText className="w-8 h-8 text-slate-400" />
                <div>
                  <p className="font-medium text-slate-900">{doc.filename}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStatusBadgeClass(doc.status)}`}>
                      {getStatusIcon(doc.status)}
                      {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                    </span>
                    <span className="text-xs text-slate-500">
                      {new Date(doc.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
              <div className="text-right">
                {doc.chunk_count !== undefined && (
                  <p className="text-sm text-slate-600">
                    {doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
