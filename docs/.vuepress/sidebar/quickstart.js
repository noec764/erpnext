module.exports = function getIntroductionSidebar (groupA) {
	return [
		{
			title: groupA,
			collapsable: false,
			children: [
				'/dokie/introduction/',
				'/dokie/setting-up/'
			]
		}
	]
}