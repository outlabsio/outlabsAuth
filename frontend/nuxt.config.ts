// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: ["@nuxt/eslint", "@nuxt/ui-pro", "@vueuse/nuxt", "@pinia/nuxt"],

  runtimeConfig: {
    apiToken: process.env.API_TOKEN,
    public: {
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || "http://localhost:3000",
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || "http://localhost:8030",
    },
  },

  devtools: {
    enabled: true,
  },

  ssr: false,

  css: ["~/assets/css/main.css"],

  app: {
    head: {
      meta: [
        { name: "robots", content: "noindex, nofollow, noarchive, nosnippet, noimageindex" },
        { name: "googlebot", content: "noindex, nofollow, noarchive, nosnippet, noimageindex" },
      ],
    },
  },

  routeRules: {
    "/api/**": {
      cors: true,
    },
  },

  future: {
    compatibilityVersion: 4,
  },

  compatibilityDate: "2024-07-11",

  eslint: {
    config: {
      stylistic: {
        commaDangle: "never",
        braceStyle: "1tbs",
      },
    },
  },
});
