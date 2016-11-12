# ImageNetDownloader

This is a downloader for downloading all the original images for a specified **synset(including all of its hyponym)**. And the default way it organizes all the data is as follows:
		
		```
			./
				hyponym1's wnid/
					hyponym1's wnid_001.jpg
					...
					...
				hyponym2's wnid/
					hyponym2's wnid_001.jpg
					...
					...
				...
				...
		```
		
		
			

The download tasks are **concurrently** executed, which saves quite a few time.

Besides, it uses the **stream** mode of requests module, which means there would only be a single chunk of data in the memory (I set it to be 1024K). Thus it also saves some memory space.

