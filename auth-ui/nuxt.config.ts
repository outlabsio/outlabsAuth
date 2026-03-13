import { readFileSync } from 'node:fs'

const packageJson = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as {
  version: string
  outlabsAuth?: {
    libraryVersion?: string
    releaseStage?: string
  }
}

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2024-07-11',

  // Client-side only (SPA mode)
  ssr: false,

  devtools: {
    enabled: true
  },

  modules: [
    '@nuxt/ui',
    '@pinia/nuxt',
    '@pinia/colada-nuxt',
    '@vueuse/nuxt'
  ],

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
      authApiPrefix: process.env.NUXT_PUBLIC_AUTH_API_PREFIX || '/v1',
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || 'http://localhost:3000',
      uiVersion: packageJson.version,
      authLibraryVersion: packageJson.outlabsAuth?.libraryVersion || 'unknown',
      releaseStage: packageJson.outlabsAuth?.releaseStage || 'alpha'
    }
  }
})
