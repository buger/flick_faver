var EndlessPhotoScroller = Class.create({	
	initialize: function(page_type, starting_page){
		if(page_type == undefined)
			page_type = 'simple'
				
		if(starting_page == undefined)
			starting_page = 0
			
		
		this.current_page = starting_page
		this.page_type = page_type
		this.loading = false	
		
		this.layout = '501'
		
		if($('skill_checkbox'))
			this.difficulty = $('skill_checkbox').checked == true ? 100 : 101 
		else
			this.difficulty = 101
		
		if(this.page_type == 'simple'){
			this.container = $('photos_table')
		}else if(this.page_type == 'main_big'){
			this.container = $('photos_container')					
		}				
		
		document.observe('difficulty:changed', this.difficultyChangeObserver.bind(this))	
	},
	
	clear:function(){
		this.container.update('')
		this.current_page = 0
		this.loading = false
		this.last_photo_id = undefined		
	},
	
	difficultyChangeObserver:function(evt){
		var checked = evt.memo
		
		if(checked == true){			
			this.difficulty = 100
		}else{
			this.difficulty = 101
		}
		
		this.clear()		
		this.loadPhotos()
	},
	
	changeLayout:function(layout){
		this.layout = layout
		
		this.clear()		
		this.loadPhotos()
	},
	
	getSrollDimensions: function(){
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
	},
	
	loadPhotos: function(repeat_counter) {				
		if (!this.loading) {			
			this.loading = true
			
			if (this.current_page == undefined)
				this.current_page = 0

			$('loader').show()

			var url = "/photos/" + (this.current_page + 1)
			
			params = $H({})
			
			params.set('page_type', this.page_type)
			params.set('difficulty', this.difficulty)
			params.set('layout', this.layout)			
										
			if (this.last_photo_id)
				params.set('last_photo_id', this.last_photo_id)						
			
			onSuccess = function(response) {
				try{
					responseText = response.responseText

					if (responseText.blank()) {
						if (repeat_counter == undefined)
							repeat_counter = 0

						if (this.current_page == 0) {
							if (repeat_counter < 10) {
								this.loadPhotos.delay(1, repeat_counter + 1)
							} else {
								$('loader').update("Something went wrong. Try to refresh page")
							}
						} else {
							$('loader').update("The End :)")
						}
					} else {
						$('loader').hide()
						this.current_page += 1
						
						regexp = /photo_id="(.*)"/
						match = response.responseText.match(regexp)
						
						if (match && match[1]){
							this.last_photo_id = match[1]							                           
						}else{
							this.last_photo_id = undefined
							this.the_end = true
						}
							
						$(this.container).insert({
							bottom : response.responseText
						})
					}

					this.loading = false
				}catch(e){
					alert(e)
				}
			}
				
			new Ajax.Request(url,
				{
					parameters: params,
					onSuccess : onSuccess.bind(this)
				})
		}
	},
	
	onScroll: function(){
		if(!this.the_end){
			var scroll_dimensions = this.getSrollDimensions()
			var scroll_offset = document.body.scrollTop
			var window_height = typeof (window.innerWidth) == 'number' ? window.innerWidth
					: document.body.clientHeight
					
			if ((scroll_offset + window_height + 400) > scroll_dimensions[1]) {
				this.loadPhotos()
			}			
		}
	}
})

document.observe("dom:loaded", function() {
	var endless_scroller;
	
	if(document.getElementById('photos_container')){
		var endless_scroller = new EndlessPhotoScroller('main_big', 1)
	} else if(document.getElementById('photos_table')) {
		var endless_scroller = new EndlessPhotoScroller()
		endless_scroller.loadPhotos()
	}
	
	if(endless_scroller)
		window.onscroll = endless_scroller.onScroll.bind(endless_scroller)	
});