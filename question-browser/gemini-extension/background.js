chrome.action.onClicked.addListener(async () => {
  const url = chrome.runtime.getURL('manager.html');
  const tabs = await chrome.tabs.query({url});
  if (tabs.length) await chrome.tabs.update(tabs[0].id, {active: true});
  else await chrome.tabs.create({url});
});
