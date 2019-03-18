const getIntroductionSidebar = require('./sidebar/quickstart.js')

module.exports = {
	title: 'Dokie',
	description: 'Documentation for Dokie',
	locales: {
	  '/': {
		lang: 'en-US',
		title: 'Dokie',
		description: 'Dokie'
	  },
	  '/fr/': {
		lang: 'fr-FR',
		title: 'Dokie',
		description: 'Dokie'
	  }
	},
	head: [
		['link', { rel: 'icon', href: `/logo.png` }],
		['link', { rel: 'manifest', href: '/manifest.json' }],
		['meta', { name: 'theme-color', content: '#3eaf7c' }],
		['meta', { name: 'apple-mobile-web-app-capable', content: 'yes' }],
		['meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black' }],
		['link', { rel: 'apple-touch-icon', href: `/icons/apple-touch-icon-152x152.png` }],
		['link', { rel: 'mask-icon', href: '/icons/safari-pinned-tab.svg', color: '#3eaf7c' }],
		['meta', { name: 'msapplication-TileImage', content: '/icons/msapplication-icon-144x144.png' }],
		['meta', { name: 'msapplication-TileColor', content: '#000000' }]
	],
	themeConfig: {
		repo: 'https://gitlab.com/dokie/dokie',
		editLinks: true,
		locales: {
			'/': {
				label: 'English',
				lastUpdated: 'Last Updated',
				selectText: 'Languages',
				editLinkText: 'Edit this page on Gitlab',
				lastUpdated: 'Last Updated',
				nav: require('./nav/en'),
				sidebar: {
				'/dokie/': getIntroductionSidebar('Dokie')
				}
			},
			'/fr/': {
				label: 'Français',
				lastUpdated: 'Dernière mise à jour',
				selectText: 'Langues',
				editLinkText: 'Modifier cette page sur Gitlab',
				lastUpdated: 'Dernière mise à jour',
				nav: require('./nav/fr'),
				sidebar: {
				'/fr/dokie/': getIntroductionSidebar('Dokie')
				}
			}
		}
	}
}