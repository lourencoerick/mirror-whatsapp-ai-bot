/** @type {import("pliny/config").PlinyConfig } */
const siteMetadata = {
  title: 'Automatize suas vendas com IA 24/7 | Lambda Labs',
  author: 'Erick',
  headerTitle: 'Lambda Labs',
  description: 'Venda mais no WhatsApp com IA: automatize, qualifique leads e atenda melhor.',
  language: 'pt-br',
  theme: 'system', // system, dark ou light
  siteUrl: 'https://lambdalabs.com.br',
  // siteRepo: 'https://github.com/lambda-labs-ai',
  siteLogo: `${process.env.BASE_PATH || ''}/logo.png`,
  socialBanner: `${process.env.BASE_PATH || ''}/social-banner.png`,
  email: 'contato@lambda-labs.ai',
  // github: 'https://github.com/lambda-labs-ai',
  // linkedin: 'https://www.linkedin.com/company/lambda-labs-ai',
  // youtube: 'https://youtube.com/@lambdalabs-ai',
  // instagram: 'https://www.instagram.com/lambda.labs.ai',
  locale: 'pt-BR',
  stickyNav: false,
  
  analytics: {
    umamiAnalytics: {
      umamiWebsiteId: process.env.NEXT_UMAMI_ID,
    },
  },

  newsletter: {
    provider: 'buttondown',
  },
  
  comments: {
    provider: 'giscus',
    giscusConfig: {
      repo: process.env.NEXT_PUBLIC_GISCUS_REPO,
      repositoryId: process.env.NEXT_PUBLIC_GISCUS_REPOSITORY_ID,
      category: process.env.NEXT_PUBLIC_GISCUS_CATEGORY,
      categoryId: process.env.NEXT_PUBLIC_GISCUS_CATEGORY_ID,
      mapping: 'pathname',
      reactions: '1',
      metadata: '0',
      theme: 'light',
      darkTheme: 'transparent_dark',
      themeURL: '',
      lang: 'pt',
    },
  },
  
  search: {
    provider: 'kbar',
    kbarConfig: {
      searchDocumentsPath: `${process.env.BASE_PATH || ''}/search.json`,
    },
  },
};

module.exports = siteMetadata;
