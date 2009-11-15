function scrollDimensions() {
	var dimensions = new Array(2)

	if (window.innerHeight && window.scrollMaxY) {
		dimensions[0] = document.body.scrollWidth
		dimensions[1] = window.innerHeight + window.scrollMaxY
	} else if (document.body.scrollHeight > document.body.offsetHeight) {
		dimensions[0] = document.body.scrollWidth
		dimensions[1] = document.body.scrollHeight
	} else {
		dimensions[0] = document.body.offsetWidth
		dimensions[1] = document.body.offsetHeight
	}

	return (dimensions)
}

function scroll() {
	var scroll_dimensions = scrollDimensions()
	var scroll_offset = document.body.scrollTop
	var window_height = typeof (window.innerWidth) == 'number' ? window.innerWidth
			: document.body.clientHeight

	if ((scroll_offset + window_height + 400) > scroll_dimensions[1]) {
		loadPhotos()
	}
}

function loadPhotos(repeat_counter) {
	if (!document.loading) {
		document.loading = true

		if (document.current_page == undefined)
			document.current_page = 0

		$('loader').show()

		var url = "/photos/" + (document.current_page + 1)
		if (document.last_photo_id)
			url += "?last_photo_id=" + document.last_photo_id

		new Ajax.Request(
				url,
				{
					onSuccess : function(response) {
						responseText = response.responseText

						if (responseText.blank()) {
							if (repeat_counter == undefined)
								repeat_counter = 0

							if (document.current_page == 0) {
								if (repeat_counter < 10) {
									loadPhotos.delay(1, repeat_counter + 1)
								} else {
									$('loader')
											.update(
													"Something went wrong. Try to refresh page")
								}
							} else {
								$('loader').update("The End :)")
							}
						} else {
							$('loader').hide()
							document.current_page += 1

							regexp = /photo_id="(.*)"/
							match = response.responseText.match(regexp)

							if (match[1])
								document.last_photo_id = match[1]

							$('photos_table').insert( {
								bottom : response.responseText
							})
						}

						document.loading = false
					}
				})
	}
}

document.observe("dom:loaded", function() {
  // initially hide all containers for tab content
	loadPhotos()
	
	window.onscroll = scroll;
});