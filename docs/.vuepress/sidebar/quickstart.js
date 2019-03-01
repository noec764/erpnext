module.exports = function getIntroductionSidebar (groupA) {
	return [
		{
			title: groupA,
			collapsable: false,
			children: [
				'/dooks/introduction/',
				'/dooks/setting-up/'
			]
		}
	]
}