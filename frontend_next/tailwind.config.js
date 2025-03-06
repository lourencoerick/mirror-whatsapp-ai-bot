// tailwind.config.js
module.exports = {
  purge: {
    content: ["./src/**/*.{js,jsx,ts,tsx}"],
    options: {
      safelist: ["font-bold"],
    },
  },
  theme: {
    extend: {
      colors: {
        'whatsapp-green': '#25D366',
      },
    },
  },
  plugins: [],
}
