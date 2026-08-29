import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'

import { Layout } from '@/components/layout'
import { ThemeProvider } from '@/components/theme-provider'
import { countPosts } from '@/lib/api'
import { HomePage } from '@/pages/HomePage'
import { PostDetailPage } from '@/pages/PostDetailPage'
import { PostsPage } from '@/pages/PostsPage'

function AppRoutes() {
  const [postCount, setPostCount] = useState(0)

  const refreshCount = useCallback(async () => {
    try {
      setPostCount(await countPosts())
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    refreshCount()
  }, [refreshCount])

  return (
    <Layout postCount={postCount}>
      <Routes>
        <Route path="/" element={<HomePage postCount={postCount} onPostChange={refreshCount} />} />
        <Route
          path="/posts"
          element={<PostsPage onDelete={() => refreshCount()} />}
        />
        <Route
          path="/posts/:id"
          element={<PostDetailPage onDelete={() => refreshCount()} />}
        />
      </Routes>
      <Toaster position="bottom-right" richColors />
    </Layout>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </ThemeProvider>
  )
}
