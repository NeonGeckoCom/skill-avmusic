
# <img src='https://0000.us/klatchat/app/files/neon_images/icons/neon_skill.png' card_color="#FF8600" width="50" style="vertical-align:bottom">AVmusic  
  
## Summary  
  
Play a song or video requested by the user.

## Description  
  
The skill provides the functionality to playback any audio or video requested by the user. No need to specify the 
location of the files or register any accounts. Just say what you would like to listen to and enjoy.  
  
AVmusic implements full integration of youtube_dl services and supports requests including but not limited to:
  
- Music bands  
      
- Albums  
  
- Playlists  
      
- Specific songs  
      
- Radio  
      
- News clips  
      
- Tutorials  
      
- Mixes  
      
- Publicly available episodes of TV shows  
      
- Publicly available movies  
      
- Short clips  
      
  
AVmusic supports audio commands to stop, pause, and resume the playback of the currently playing video. If you requested a playlist, [you will see a list of available titles](#picture) on the left side of your opened video-player window.  
  
As of now, you can only have one instance (window) of MPV open at a time. If you invoke another playback request while watching something else, your current window will be closed and the new one will popup in its place.  
  
If you are typing your command in the terminal instead of audibly speaking it, don’t worry about the typos or spelling - AVmusic will correct it for you.  
  
    
  
  
## Examples  
  
First, make your request:  
  
Say `“Hey Neon”` if you are in the wake words mode, otherwise include `"Neon"` at the beginning of your request. Make
sure to follow the pattern of `"AV play artist or song name"` or `"play some artist or song name"` and add `"music"` or
any combination of the following commands to your request: `“playlist, repeat, video”`.  
For example:
  
- "play some Imagine Dragons music on repeat"
      
- "av play study music playlist"
      
- “play a cookie baking tutorial video" 
      
  
Secondly, wait for Neon to reply with `“Would you like me to play it now?”`. Reply with a positive answer, such as
`"yes", "continue", "go ahead"`, or a negative one, such as `"no", "nevermind", "cancel"`.
  
If you opt for a negative answer, Neon will ask you to `let me know if you change your mind` later and want to play the
requested video or audio at a different time. This option has a timeout of 50 seconds. Neon will forget about that
request after the timeout. If you do wish to play the requested playback, simply say `“Actually, go ahead”` and the
skill will continue processing.
  
After Neon hears the positive confirmation from you, the requested video or audio will open. If you were skipping wake
words, the device will switch to the wake words required mode. It will switch back to your preferred setting after the
playback is done or cancelled.
  
At this point you can say commands like `pause`, `resume`, `next`, and `previous`. Each command has a 30 second timeout.
  
  
`“Hey Neon, stop”` will close the window and all subprocesses associated with it.
  
If there is a problem with locating the requested audio or video at any point, Neon will prompt you to try again with a different request by saying `“Actually, i could not find the music you were looking for. Could you try again?“` If the failed request worked previously, please refer to the [Troubleshooting](#troubleshooting)  

## Troubleshooting
There is a [known issue](https://github.com/ytdl-org/youtube-dl/issues/154) for youtube_dl, where the playback for certain videos and audio files will be temporarily unavailable if you request to listen to the same song and/or video multiple times in a row over a few days. The solution is to avoid requesting the same playback over and over again, try to word your request differently, or wait some time for the limitations to wear off.

Additionally, youtube_dl is currently under active development. Make sure to stay up-to-date by running Neon's update script or use the [manual requirements instructions](#requirements) to do it yourself.

## Contact Support
Use [this link](https://neongecko.com/ContactUs) or
[submit an issue on GitHub](https://help.github.com/en/articles/creating-an-issue)

## Credits
[reginaneon](https://github.com/reginaneon)
[NeonGeckoCom](https://github.com/NeonGeckoCom)
[augustnmonteiro](https://github.com/augustnmonteiro)

## Tags
#NeonGecko Original
#NeonAI
#Music
#Videos
#Common Play