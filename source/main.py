# TO-DO: Discord to Minecraft relay - Datagram unix sockets, steal bridge code
# TO-DO: #anonymous relay - Client-only slash commands?
# TO-DO: #market channel buy/sell listings for the Minecraft server
# TO-DO: Logging for every gateway event.
# TO-DO: Basic music bot to replace Groovy.
# TO-DO: /minecraft slash command to fetch Minecraft server info & status.
# TO-DO: Store member information and statistics in SQLite database.
# TO-DO: Repost detection.
# TO-DO: Seperate files for logging functions.

# Import dependencies
import os, re, datetime
import discord, requests, emoji, colorthief
import relay, helpers

# Set global constant variables
LOG_PATH = "logs/{0}.log"
PRIMARY_SERVER_ID = 240167618575728644
MARKET_CHANNEL_ID = 852114085750636584
RELAY_CHANNEL_ID = 851437359237169183
STAGE_CHANNEL_ID = 826908363392680026
HISTORY_CHANNEL_ID = 576904701304635405
LURKER_ROLE_ID = 807559722127458304
YEAR_2021_ROLE_ID = 804869340225863691

# Define global variables
primaryServer = None
logFile = None
auditLogCache = {}
bot = discord.Client(
	max_messages = 1000000, # Cache way more messages 
	intents = discord.Intents.all(), # Receive all events
	allowed_mentions = discord.AllowedMentions.none() # Prevent mentioning anyone
)

# Setup the relay
relay.setup( "discordbot" )

# For logging nessages to the console and file
def consoleLog( message ):
	# Rules of logging:
	# * User controlled values should be wrapped in single quotes
	# * Additional information comes after primary information in brackets
	# * Applicable values should be prefixed or suffixed to indicate what they mean
	# * Lists should be wrapped in square brackets
	# * Anything that is void should be replaced with a placeholder hyphen
	# * Do not relog past information, just give an ID to refer back to it
	# * Respect user privacy and redact information for direct messages

	# The full message to log
	fullMessage = "[{datetime:%d-%m-%Y %H:%M:%S.%f %z}] {message}".format(
		datetime = datetime.datetime.now( datetime.timezone.utc ),
		message = message
	)

	# Log to the file
	logFile.write( fullMessage + "\n" )
	logFile.flush()

	# Log to the console
	print( fullMessage )

def cleanMessageForLogs( content ):
	# Escape codeblocks
	content = re.sub( r"`{3}", r"\`\`\`", content )

	# Clean custom emojis
	content = re.sub( r"<a?:(\w+):(\d+)>", r":\1:", content )

	# Clean unicode emojis
	content = emoji.demojize( content )

	# Shorten it with an elipsis if needed
	content = ( content if len( content ) <= 1024 else content[ :( 1024 - 6 - 3 ) ] + "..." ) # -6 for code block, -3 for elipsis dots

	# Return the final result in a codeblock
	return "```{0}```".format( content )

def formatAttachmentsForLogs( attachments ):
	return ( "\n".join( [ "[{attachmentName} {attachmentDimensions}({attachmentSize} KiB)]({attachmentURL}) [[Cache]]({attachmentProxyURL})".format(
		attachmentName = attachment.filename,
		attachmentSize = round( attachment.size / 1024, 2 ),
		attachmentDimensions = ( "({attachmentWidth}x{attachmentHeight}) ".format(
			attachmentWidth = attachment.width,
			attachmentHeight = attachment.height
		) if attachment.width else "" ),
		attachmentURL = attachment.url,
		attachmentProxyURL = attachment.proxy_url
	) for attachment in message.attachments ] ) )

async def discordLog( title, fields ):
	logsChannel = primaryServer.get_channel( HISTORY_CHANNEL_ID )
	rightNow = datetime.datetime.now( datetime.timezone.utc )

	logEmbed = discord.Embed(
		title = title,
		color = primaryServer.me.color
	)

	for field in fields:
		logEmbed.add_field(
			name = field[ 0 ],
			value = field[ 1 ],
			inline = field[ 2 ]
		)

	logEmbed.set_footer(
		text = "{datetime:%A} {datetime:%-d}{daySuffix} {datetime:%B} {datetime:%Y} at {datetime:%-H}:{datetime:%M}:{datetime:%S} {datetime:%Z}".format(
			datetime = rightNow,
			daySuffix = helpers.daySuffix( rightNow.day )
		)
	)

	await logsChannel.send( embed = logEmbed )

async def fetchMessageDeleter( guildID, channelID, authorID ):
	rightNow = datetime.datetime.now( datetime.timezone.utc )
	fiveSecondsAgo = rightNow - datetime.timedelta( seconds = 5 )

	response = await helpers.httpRequest( "GET", "https://discord.com/api/v9/guilds/{guildID}/audit-logs".format(
		guildID = guildID
	), params = {
		"limit": 100,
		"action_type": 72 # MESSAGE_DELETE
	}, headers = {
		"Accept": "application/json",
		"Authorization": "Bot {0}".format( os.environ[ "BOT_TOKEN" ] ),
		"User-Agent": "viral32111's discord bot (https://viral32111.com/contact; contact@viral32111.com)",
		"From": "contact@viral32111.com"
	} )

	response.raise_for_status()
	results = response.json()

	for entry in results[ "audit_log_entries" ]:
		if int( entry[ "options" ][ "channel_id" ] ) != channelID: continue
		
		if authorID:
			if int( entry[ "target_id" ] ) != authorID: continue

		when = datetime.datetime.fromtimestamp( ( ( int( entry[ "id" ] ) >> 22 ) + 1420070400000 ) / 1000, tz = datetime.timezone.utc )

		if when > fiveSecondsAgo:
			auditLogCache[ entry[ "id" ] ] = entry[ "options" ][ "count" ]

			if authorID:
				return int( entry[ "user_id" ] )
			else:
				return int( entry[ "user_id" ] ), int( entry[ "target_id" ] )
		else:
			if entry[ "options" ][ "count" ] > auditLogCache[ entry[ "id" ] ]:
				auditLogCache[ entry[ "id" ] ] = entry[ "options" ][ "count" ]

				if authorID:
					return int( entry[ "user_id" ] )
				else:
					return int( entry[ "user_id" ] ), int( entry[ "target_id" ] )

			auditLogCache[ entry[ "id" ] ] = entry[ "options" ][ "count" ]

	if authorID:
		return authorID
	else:
		return authorID, authorID

# Calculate and open the log file
logNumber = 1
while os.path.isfile( LOG_PATH.format( logNumber ) ): logNumber += 1
logFile = open( LOG_PATH.format( logNumber ), "w" )
consoleLog( "Opened log file '{logPath}'.".format(
	logPath = logFile.name
) )

# Runs when the session is opened
async def on_connect():
	# Log a message to the console
	consoleLog( "Connected!" )

# Runs when the session is closed
async def on_disconnect():
	# Log a message to the console
	consoleLog( "Disconnected." )

# Runs when the session is reopened
async def on_resume():
	# Log a message to the console
	consoleLog( "Resumed!" )

# Runs when a message is received...
async def on_message( message ):
	# Ignore message pinned and member joined messages since we have events for those
	if message.type == discord.MessageType.pins_add or message.type == discord.MessageType.new_member: return

	# Log this event to the console
	consoleLog( "{authorName} ({authorNick}, {authorTag}, {authorID}) sent {messageType} message {messageContent} [{attachments}] [{stickers}] [{embeds}] {application} ({messageLength}, {messageID}) {messageReference}in {location}.".format(
		authorName = ( "'{0}'".format( emoji.demojize( message.author.name ) ) if message.guild else "-HIDDEN-" ),
		authorNick = ( "'{0}'".format( emoji.demojize( message.author.nick ) ) if not message.author.bot and message.guild and message.author.nick else "-" ),
		authorTag = ( "-" if message.webhook_id else ( "#{0}".format( message.author.discriminator ) if message.guild else "-HIDDEN-" ) ),
		authorID = ( message.author.id if message.guild else "-HIDDEN-" ),

		messageType = ( "system" if message.is_system() and not message.type == discord.MessageType.reply else ( "spoken" if message.tts else "regular" ) ),

		messageContent = ( "'{0}'".format( emoji.demojize( message.system_content ) ) if message.is_system() and not message.type == discord.MessageType.reply else ( ", ".join( [ ( "'{0}'".format( emoji.demojize( line ) ) if line != "" else "-" ) for line in message.content.split( "\n" ) ] ) if message.content else "-" ) ),
		attachments = (
			( ", ".join( [ "'{attachmentName}' ({attachmentType}, {attachmentSize}B, {attachmentWidth}, {attachmentHeight}, {attachmentID})".format(
				attachmentName = attachment.filename,
				attachmentType = ( attachment.content_type or "-" ),
				attachmentSize = attachment.size,
				attachmentWidth = ( "{0}px".format( attachment.width ) if attachment.width else "-" ),
				attachmentHeight = ( "{0}px".format( attachment.height ) if attachment.height else "-" ),
				attachmentID = attachment.id
			) for attachment in message.attachments ] ) ) if len( message.attachments ) > 0 else ""
		),
		stickers = (
			( ", ".join( [ "'{stickerName}' ({stickerType}, {packID}, {stickerID})".format(
				stickerName = sticker.name,
				stickerType = sticker.format,
				packID = sticker.pack_id,
				stickerID = sticker.id
			) for sticker in message.stickers ] ) ) if len( message.stickers ) > 0 else ""
		),
		embeds = ( ", ".join( [ str( embed.to_dict() ) for embed in message.embeds ] ) if len( message.embeds ) > 0 else "" ),
		application = ( str( message.application ) if message.application else "-" ),
		messageLength = len( message.content ),
		messageID = ( message.id if message.guild else "-HIDDEN-" ),

		messageReference = ( "referencing {{{messageID}}} ({channelID}, {serverID}) ".format(
			messageID = ( message.reference.message_id if message.guild else "-HIDDEN-" ),
			channelID = ( message.reference.channel_id if message.guild else "-HIDDEN-" ),
			serverID = ( message.reference.guild_id or "-" )
		) if message.reference else "" ),

		location = (
			( "'{serverName}' ({serverID}) -> '{categoryName}' ({categoryID}) -> '#{channelName}' ({channelID})".format(
				serverName = emoji.demojize( message.guild.name ),
				serverID = message.guild.id,
				
				categoryName = emoji.demojize( message.channel.category.name ),
				categoryID = message.channel.category.id,

				channelName = emoji.demojize( message.channel.name ),
				channelID = message.channel.id
			) if message.channel.category else "'{serverName}' ({serverID}) -> '#{channelName}' ({channelID})".format(
				serverName = emoji.demojize( message.guild.name ),
				serverID = message.guild.id,
				
				channelName = emoji.demojize( message.channel.name ),
				channelID = message.channel.id
			) ) if message.guild else "direct messages"
		)
	) )

	# Ignore bot messages
	if message.author.bot: return

	# Ignore messages without any content
	if len( message.content ) == 0: return

	# Is this the Minecraft relay channel?
	if message.channel.id == RELAY_CHANNEL_ID:

		# Attempt to relay the message to the Minecraft server
		try:
			await relay.send( relay.type.message, {
				"username": emoji.demojize( message.author.display_name ),
				"content": emoji.demojize( message.clean_content.replace( "\n", " " ) ),
				"color": message.author.color.value
			}, "minecraft" )

		# Notify the user of an error if one happens
		except Exception as exception:
			await message.reply( ":interrobang: Your message could not be sent due to an internal error!" )
			raise exception

# Runs when a message is deleted...
async def on_raw_message_delete( rawMessage ):
	# TO-DO: Make it work for non-cached messages!
	if not rawMessage.cached_message: return

	# Fetch the member/user that deleted this message
	if rawMessage.guild_id:
		server = bot.get_guild( rawMessage.cached_message.guild.id )
		deleterID = await fetchMessageDeleter( rawMessage.cached_message.guild.id, rawMessage.cached_message.channel.id, rawMessage.cached_message.author.id )
		deleter = ( server.get_member( deleterID ) if deleterID else None )
	else:
		deleter = rawMessage.cached_message.author

	# Log this event to the console
	consoleLog( "{deleterName} ({deleterNick}, {deleterTag}, {deleterID}) deleted {messageType} message {{{messageID}}} sent by {authorName} ({authorNick}, {authorTag}, {authorID}) in {location}.".format(
		deleterName = ( ( "'{0}'".format( emoji.demojize( deleter.name ) ) if deleter else "-" ) if rawMessage.cached_message.guild else "-HIDDEN-" ),
		deleterNick = ( "'{0}'".format( emoji.demojize( deleter.nick ) ) if rawMessage.guild_id and deleter and deleter.nick else "-" ),
		deleterTag = ( ( "#{0}".format( deleter.discriminator ) if deleter else "-" ) if rawMessage.cached_message.guild else "-HIDDEN-" ),
		deleterID = ( ( deleter.id if deleter else "-" ) if rawMessage.cached_message.guild else "-HIDDEN-" ),

		messageType = ( "system" if rawMessage.cached_message.is_system() and not rawMessage.cached_message.type == discord.MessageType.reply else ( "spoken" if rawMessage.cached_message.tts else "regular" ) ),
		messageID = rawMessage.cached_message.id,

		authorName = ( "'{0}'".format( emoji.demojize( rawMessage.cached_message.author.name ) ) if rawMessage.cached_message.guild else "-HIDDEN-" ),
		authorNick = ( "'{0}'".format( emoji.demojize( rawMessage.cached_message.author.nick ) ) if not rawMessage.cached_message.author.bot and rawMessage.cached_message.guild and rawMessage.cached_message.author.nick else "-" ),
		authorTag = ( "-" if rawMessage.cached_message.webhook_id else ( "#{0}".format( rawMessage.cached_message.author.discriminator ) if rawMessage.cached_message.guild else "-HIDDEN-" ) ),
		authorID = ( rawMessage.cached_message.author.id if rawMessage.cached_message.guild else "-HIDDEN-" ),

		location = (
			( "'{serverName}' ({serverID}) -> '{categoryName}' ({categoryID}) -> '#{channelName}' ({channelID})".format(
				serverName = emoji.demojize( rawMessage.cached_message.guild.name ),
				serverID = rawMessage.cached_message.guild.id,
				
				categoryName = emoji.demojize( rawMessage.cached_message.channel.category.name ),
				categoryID = rawMessage.cached_message.channel.category.id,

				channelName = emoji.demojize( rawMessage.cached_message.channel.name ),
				channelID = rawMessage.cached_message.channel.id
			) if rawMessage.cached_message.channel.category else "'{serverName}' ({serverID}) -> '#{channelName}' ({channelID})".format(
				serverName = emoji.demojize( rawMessage.cached_message.guild.name ),
				serverID = rawMessage.cached_message.guild.id,
				
				channelName = emoji.demojize( rawMessage.cached_message.channel.name ),
				channelID = rawMessage.cached_message.channel.id
			) ) if rawMessage.cached_message.guild else "direct messages"
		)
	) )

	# Ignore Direct Messages
	if not rawMessage.cached_message.guild: return

	# Ignore the history channel
	if rawMessage.cached_message.channel.id == HISTORY_CHANNEL_ID: return

	# Ignore private channels
	if rawMessage.cached_message.channel.overwrites_for( rawMessage.cached_message.guild.default_role ).pair()[ 1 ].view_channel == True: return

	# Create a list for the embed fields
	logFields = [
		[ "Author", rawMessage.cached_message.author.mention, True ],
		[ "Deleter", ( deleter.mention if deleter else "Unknown" ), True ],
		[ "Channel", rawMessage.cached_message.channel.mention, True ]
	]

	# Add the embed field for the message, if applicable
	if len( rawMessage.cached_message.clean_content ) > 0:
		logFields.append( [ "Message", cleanMessageForLogs( rawMessage.cached_message.clean_content ), False ] )
	else:
		logFields.append( [ "Message", "Content not displayable.", False ] )

	# Add the embed field for the attachments, if applicable
	if len( rawMessage.cached_message.attachments ) > 0:
		logFields.append( [ "Attachments", formatAttachmentsForLogs( rawMessage.cached_message.attachments ), False ] )

	# Log this event in the logging channel
	await discordLog( "Message Deleted", logFields )

	# For uncached messages:
	#deletedByID, sentByID = await fetchMessageDeleter( rawMessage.guild_id, rawMessage.channel_id, None )
	#if sentByID:
	#	sentBy = bot.get_user( sentByID )
	#	logContents.append( [ "Sent By", sentBy.mention, True ] )
	#else:
	#	logContents.append( [ "Sent By", "Unknown!", True ] )
	#if deletedByID:
	#	deletedBy = bot.get_user( deletedByID )
	#	logContents.append( [ "Deleted By", deletedBy.mention, True ] )
	#else:
	#	logContents.append( [ "Deleted By", "Author", True ] )
	#logContents.append( [ "Channel", "<#{0}>".format( rawMessage.channel_id ), True ] )
	#logContents.append( [ "Message", "Unknown!", False ] )

# Runs when a message is edited...
async def on_raw_message_edit( rawMessage ):
	# TO-DO: Make it work for non-cached messages!
	if not rawMessage.cached_message: return

	# TO-DO: Make this work for embed updates and other edits!
	if not "content" in rawMessage.data: return

	# Log this to the console
	consoleLog( "{authorName} ({authorNick}, {authorTag}, {authorID}) edited {messageType} message {{{messageID}}} to {messageContent} ({messageLength}) in {location}.".format(
		authorName = ( "'{0}'".format( emoji.demojize( rawMessage.cached_message.author.name ) ) if rawMessage.cached_message.guild else "-HIDDEN-" ),
		authorNick = ( "'{0}'".format( emoji.demojize( rawMessage.cached_message.author.nick ) ) if not rawMessage.cached_message.author.bot and rawMessage.cached_message.guild and rawMessage.cached_message.author.nick else "-" ),
		authorTag = ( "-" if rawMessage.cached_message.webhook_id else ( "#{0}".format( rawMessage.cached_message.author.discriminator ) if rawMessage.cached_message.guild else "-HIDDEN-" ) ),
		authorID = ( rawMessage.cached_message.author.id if rawMessage.cached_message.guild else "-HIDDEN-" ),

		messageType = ( "spoken" if rawMessage.cached_message.tts else "regular" ),
		messageID = rawMessage.cached_message.id,
		messageContent = ( ", ".join( [ ( "'{0}'".format( emoji.demojize( line ) ) if line != "" else "-" ) for line in rawMessage.data[ "content" ].split( "\n" ) ] ) if rawMessage.data[ "content" ] else "-" ),
		messageLength = len( rawMessage.data[ "content" ] ),

		location = (
			( "'{serverName}' ({serverID}) -> '{categoryName}' ({categoryID}) -> '#{channelName}' ({channelID})".format(
				serverName = emoji.demojize( rawMessage.cached_message.guild.name ),
				serverID = rawMessage.cached_message.guild.id,
				
				categoryName = emoji.demojize( rawMessage.cached_message.channel.category.name ),
				categoryID = rawMessage.cached_message.channel.category.id,

				channelName = emoji.demojize( rawMessage.cached_message.channel.name ),
				channelID = rawMessage.cached_message.channel.id
			) if rawMessage.cached_message.channel.category else "'{serverName}' ({serverID}) -> '#{channelName}' ({channelID})".format(
				serverName = emoji.demojize( rawMessage.cached_message.guild.name ),
				serverID = rawMessage.cached_message.guild.id,
				
				channelName = emoji.demojize( rawMessage.cached_message.channel.name ),
				channelID = rawMessage.cached_message.channel.id
			) ) if rawMessage.cached_message.guild else "direct messages"
		)
	) )

	# Ignore Direct Messages
	if not rawMessage.cached_message.guild: return

	# Ignore the history channel
	if rawMessage.cached_message.channel.id == HISTORY_CHANNEL_ID: return

	# Ignore private channels
	if rawMessage.cached_message.channel.overwrites_for( rawMessage.cached_message.guild.default_role ).pair()[ 1 ].view_channel == True: return

	# Create a list for the embed fields
	logFields = [
		[ "Author", rawMessage.cached_message.author.mention, True ],
		[ "Channel", rawMessage.cached_message.channel.mention, True ]
	]

	# Add the embed field for the old content, if applicable
	if len( rawMessage.cached_message.clean_content ) > 0:
		logFields.append( [ "Old Message", cleanMessageForLogs( rawMessage.cached_message.clean_content ), False ] )
	else:
		logFields.append( [ "Old Message", "Content not displayable.", False ] )

	# Add the embed field for the new content, if applicable
	# TO-DO: This needs to be human friendly/clean content too!
	if len( rawMessage.data[ "content" ] ) > 0:
		logFields.append( [ "New Message", cleanMessageForLogs( rawMessage.data[ "content" ] ), False ] )
	else:
		logFields.append( [ "New Message", "Content not displayable.", False ] )

	# Log this event in the history channel
	await discordLog( "Message Edited", logFields )

async def on_member_join( member ):
	# TO-DO: h0nde has been banned from twitter, so remove this if no bots join for a few weeks?
	if re.search( r"twitter\.com\/h0nde", member.name, flags = re.IGNORECASE ):
		await member.add_roles( primaryServer.get_role( LURKER_ROLE_ID ), reason = "Dumb spam bot >:(" )
		return await primaryServer.system_channel.send( ":anger: {memberMention} is a dumb spam bot.".format(
			memberMention = member.mention
		) )

	await member.add_roles( primaryServer.get_role( YEAR_2021_ROLE_ID ), reason = "Member joined in 2021." )

	await primaryServer.system_channel.send( ":wave_tone1: {memberMention} joined the community!\nPlease read through the guidelines and information in {channelMention} before you start chatting..".format(
		channelMention = primaryServer.rules_channel.mention,
		memberMention = member.mention
	), allowed_mentions = discord.AllowedMentions( users = True ) )

async def on_member_remove( member ):
	await primaryServer.system_channel.send( "{memberName}#{memberTag} left the community.".format(
		memberName = member.name,
		memberTag = member.discriminator
	) )

async def on_guild_update( oldServer, newServer ):
	if oldServer.system_channel_flags.join_notifications != newServer.system_channel_flags.join_notifications: return

	serverTemplate = ( await newServer.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to server update event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_guild_channel_create( channel ):
	serverTemplate = ( await channel.guild.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to channel create event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_guild_channel_delete( channel ):
	serverTemplate = ( await channel.guild.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to channel delete event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_guild_channel_update( oldChannel, newChannel ):
	if newChannel.id == STAGE_CHANNEL_ID and newChannel.name != "Stage":
		await newChannel.edit(
			name = "Stage",
			reason = "Do not rename this channel! >:("
		)

	serverTemplate = ( await newChannel.guild.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to channel update event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_guild_role_create( role ):
	serverTemplate = ( await role.guild.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to role create event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_guild_role_delete( role ):
	serverTemplate = ( await role.guild.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to role delete event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_guild_role_update( oldRole, newRole ):
	serverTemplate = ( await newRole.guild.templates() )[ 0 ]
	await serverTemplate.sync()
	consoleLog( "Synced template '{templateName}' ({templateCode}) due to role update event.".format(
		templateName = serverTemplate.name,
		templateCode = serverTemplate.code
	) )

async def on_application_command( data ):
	if "guild_id" not in data:
		consoleLog( "{userName}#{userTag} attempted to use my commands in Direct Messages".format(
			userName = data[ "user" ][ "username" ],
			userTag = data[ "user" ][ "discriminator" ],
		) )

		return await helpers.respondToInteraction( data, 4, {
			"content": "Sorry, I do not work in Direct Messages yet! Please stick to using my commands in the server for now.",
			"flags": 64
		} )

	server = bot.get_guild( int( data[ "guild_id" ] ) )
	channel = server.get_channel( int( data[ "channel_id" ] ) )
	member = server.get_member( int( data[ "member" ][ "user" ][ "id" ] ) )

	if data[ "data" ][ "name" ] == "activity":
		if not member.voice:
			consoleLog( "{memberName}#{memberTag} attempted to start a voice activity without being in a voice channel.".format(
				memberName = member.name,
				memberTag = member.discriminator
			) )

			return await helpers.respondToInteraction( data, 4, {
				"content": "You first need to join a voice channel to start an activity!",
				"flags": 64
			} )

		if member.voice.channel.type != discord.ChannelType.voice:
			consoleLog( "{memberName}#{memberTag} attempted to start a voice activity without being in a regular voice channel.".format(
				memberName = member.name,
				memberTag = member.discriminator
			) )

			return await helpers.respondToInteraction( data, 4, {
				"content": "Only regular voice channels are supported!",
				"flags": 64
			} )

		inviteResponse = await helpers.httpRequest( "POST", "https://discord.com/api/v9/channels/{channelID}/invites".format(
			channelID = member.voice.channel.id
		), headers = {
			"Accept": "application/json",
			"Authorization": "Bot {0}".format( os.environ[ "BOT_TOKEN" ] ),
			"X-Audit-Log-Reason": "Starting activity in a voice channel."
		}, json = {
			"max_age": 3600,
			"target_type": 2,
			"target_application_id": data[ "data" ][ "options" ][ 0 ][ "value" ]
		} )

		await helpers.respondToInteraction( data, 4, {
			"content": "[Click me to start!](<https://discord.gg/{inviteCode}>) This link will expire in 1 hour.".format( inviteCode = inviteResponse.json()[ "code" ] ),
			"allowed_mentions": { "parse": [] }
		} )

		consoleLog( "{memberName}#{memberTag} started voice activity {activityID} in voice channel {channelID}: discord.gg/{inviteCode}.".format(
			memberName = member.name,
			memberTag = member.discriminator,
			activityID = data[ "data" ][ "options" ][ 0 ][ "value" ],
			channelID = member.voice.channel.id,
			inviteCode = inviteResponse.json()[ "code" ]
		) )

	elif data[ "data" ][ "name" ] == "minecraft":
		if data[ "data" ][ "options" ][ 0 ][ "name" ] == "status":
			await helpers.respondToInteraction( data, 4, {
				"content": ":no_entry_sign: no, not yet :no_entry_sign:",
				"flags": 64
			} )

		elif data[ "data" ][ "options" ][ 0 ][ "name" ] == "market":
			options = { option[ "name" ]: option[ "value" ] for option in data[ "data" ][ "options" ][ 0 ][ "options" ][ 0 ][ "options" ] }

			if data[ "data" ][ "options" ][ 0 ][ "options" ][ 0 ][ "name" ] == "create":
				# TO-DO: Input validation!
				# if title longer than 50 chars
				# if title is invisible characters/empty markdown
				# if description longer than 500 chars
				# if description is invisible characters/empty markdown
				# if image is not a valid url / does not point to a valid image
				# if message id is not valid / does not point to an existing offer

				await helpers.respondToInteraction( data, 5, {
					"content": "",
					"flags": 64
				} )

				color = server.me.color

				if "image" in options:
					thumbnailDownloadPath = await helpers.downloadImage( options[ "image" ] )
					dominantColorRed, dominantColorGreen, dominantColorBlue = colorthief.ColorThief( thumbnailDownloadPath ).get_color( quality = 3 )
					color = ( dominantColorRed * 65536 ) + ( dominantColorGreen * 256 ) + dominantColorBlue

				rightNowUTC = datetime.datetime.now( datetime.timezone.utc )

				offerMessagePayload = {
					"embed": {
						"title": options[ "title" ],
						"description": options[ "description" ],
						"color": color,
						"author": {
							"name": "{memberName}#{memberTag}".format(
								memberName = member.name,
								memberTag = member.discriminator
							),
							"icon_url": "https://cdn.discordapp.com/avatars/{memberID}/{memberAvatar}.png".format(
								memberID = member.id,
								memberAvatar = member._user._avatar
							)
						},
						"footer": {
							"text": "Offer posted on {rightNow:%A} {rightNow:%-d}{daySuffix} {rightNow:%B} {rightNow:%Y} at {rightNow:%-H}:{rightNow:%M} {rightNow:%Z}.".format(
								rightNow = rightNowUTC,
								daySuffix = helpers.daySuffix( rightNowUTC.day )
							),
							"icon_url": "https://i.imgur.com/WyrN3ml.png"
						}
					},
					"components": [
						{
							"type": 1,
							"components": [
								{
									"type": 2,
									"style": 5,
									"label": "Discord Profile",
									"url": "https://discord.com/users/{memberID}".format(
										memberID = member.id
									),
									"disabled": False
								},
								{
									"type": 2,
									"style": 4,
									"label": "Remove",
									"custom_id": "remove-{memberID}".format(
										memberID = member.id
									),
									"disabled": False
								}
							]
						}
					]
				}

				if "image" in options:
					offerMessagePayload[ "embed" ][ "thumbnail" ] = {
						"url": options[ "image" ]
					}

				offerMessageResponse = await helpers.httpRequest( "POST", "https://discord.com/api/v9/channels/{channelID}/messages".format(
					channelID = MARKET_CHANNEL_ID
				), headers = {
					"Accept": "application/json",
					"Authorization": "Bot {0}".format( os.environ[ "BOT_TOKEN" ] ),
					"X-Audit-Log-Reason": "Creating an offer in #market."
				}, json = offerMessagePayload )

				offerMessage = offerMessageResponse.json()

				return await helpers.httpRequest( "PATCH", "https://discord.com/api/v9/webhooks/{applicationID}/{interactionToken}/messages/@original".format(
					applicationID = data[ "application_id" ],
					interactionToken = data[ "token" ]
				), headers = {
					"Accept": "application/json",
					"Authorization": "Bot {0}".format( os.environ[ "BOT_TOKEN" ] ),
					"X-Audit-Log-Reason": "Updating an interaction response."
				}, json = {
					"content": "Done! Your offer has been created in <#{channelID}>.\n\nThe offer's message ID is `{messageID}`, you will need this in the future if you wish to modify it using `/minecraft market modify`. Don't worry if you forget it or lose this response, you can always get it again by right clicking on the offer's message and clicking *Copy ID*.\n\nDirect link to the offer: <{messageLink}>.".format(
						channelID = MARKET_CHANNEL_ID,
						messageID = offerMessage[ "id" ],
						messageLink = "https://discord.com/channels/{serverID}/{channelID}/{messageID}".format(
							serverID = server.id,
							channelID = MARKET_CHANNEL_ID,
							messageID = offerMessage[ "id" ],
						)
					),
					"flags": 64
				} )

			elif data[ "data" ][ "options" ][ 0 ][ "options" ][ 0 ][ "name" ] == "modify":
				# TO-DO: The date and time the offer was modified in UTC [FOOTER]

				return await helpers.respondToInteraction( data, 4, {
					"content": ":no_entry_sign: no, not yet :no_entry_sign:",
					"flags": 64
				} )

			elif data[ "data" ][ "options" ][ 0 ][ "options" ][ 0 ][ "name" ] == "remove":
				return await helpers.respondToInteraction( data, 4, {
					"content": ":no_entry_sign: no, not yet :no_entry_sign:",
					"flags": 64
				} )

async def on_message_component( data ):
	callingMemberID = int( data[ "member" ][ "user" ][ "id" ] )
	customName, customData = data[ "data" ][ "custom_id" ].split( "-" )

	await helpers.respondToInteraction( data, 6, None )

	if customName == "remove":
		if callingMemberID == int( customData ):
			# TO-DO: Removal confirmation by updating the button text

			await helpers.httpRequest( "DELETE", "https://discord.com/api/v9/channels/{channelID}/messages/{messageID}".format(
				channelID = data[ "channel_id" ],
				messageID = data[ "message" ][ "id" ]
			), headers = {
				"Authorization": "Bot {0}".format( os.environ[ "BOT_TOKEN" ] ),
				"X-Audit-Log-Reason": "Removing a #market offer message."
			} )

async def on_socket_response( payload ):
	if payload[ "t" ] == "INTERACTION_CREATE":
		if payload[ "d" ][ "type" ] == 2:
			bot.dispatch( "application_command", payload[ "d" ] )
		elif payload[ "d" ][ "type" ] == 3:
			bot.dispatch( "message_component", payload[ "d" ] )

# Runs when the bot is ready...
async def on_ready():
	# Apply changes to global variables
	global primaryServer, auditLogCache

	# Register post-ready event handlers
	bot.event( on_message )
	bot.event( on_raw_message_delete )
	bot.event( on_raw_message_edit )
	bot.event( on_member_join )
	bot.event( on_member_remove )
	bot.event( on_guild_update )
	bot.event( on_guild_channel_create )
	bot.event( on_guild_channel_delete )
	bot.event( on_guild_channel_update )
	bot.event( on_guild_role_create )
	bot.event( on_guild_role_delete )
	bot.event( on_guild_role_update )
	bot.event( on_application_command )
	bot.event( on_message_component )
	bot.event( on_socket_response )
	consoleLog( "Registered post-ready event handlers." )

	# Log a message to the console
	consoleLog( "Logged in as '{botName}' (#{botTag}, {botID}) on {serverCount} server(s): {serverList}.".format(
		botName = bot.user.name,
		botTag = bot.user.discriminator,
		botID = bot.user.id,
		serverCount = len( bot.guilds ),
		serverList = ( ", ".join( [ "'{serverName}' ({serverID})".format(
			serverName = emoji.demojize( server.name ),
			serverID = server.id
		) for server in bot.guilds ] ) )
	) )

	# Store the primary server instance for later use
	primaryServer = bot.get_guild( PRIMARY_SERVER_ID )
	consoleLog( "The primary server is '{serverName}' ({serverID}).".format(
		serverName = emoji.demojize( primaryServer.name ),
		serverID = primaryServer.id
	) )

	# Disable default join notifications on the server
	systemChannelFlags = primaryServer.system_channel_flags
	systemChannelFlags.join_notifications = False
	await primaryServer.edit(
		system_channel_flags = systemChannelFlags,
		reason = "Disable default join messages in favour of custom join messages."
	)
	consoleLog( "Disabled default join messages for '{serverName}' ({serverID}).".format(
		serverName = emoji.demojize( primaryServer.name ),
		serverID = primaryServer.id
	) )

	# Set the bot's current activity
	await bot.change_presence( activity = discord.Activity(
		name = "all of you.",
		type = discord.ActivityType.watching
	) )
	consoleLog( "Current activity set to '{activityType}' '{activityName}'.".format(
		activityType = primaryServer.me.activity.type.name.capitalize(),
		activityName = primaryServer.me.activity.name
	) )

	# Cache the current state of the Audit Log
	auditLogResponse = requests.request( "GET", "https://discord.com/api/v9/guilds/{guildID}/audit-logs".format(
		guildID = primaryServer.id
	), params = {
		"limit": 100,
		"action_type": 72 # MESSAGE_DELETE
	}, headers = {
		"Accept": "application/json",
		"Authorization": "Bot {0}".format( os.environ[ "BOT_TOKEN" ] ),
		"User-Agent": "viral32111's discord bot (https://viral32111.com/contact; contact@viral32111.com)",
		"From": "contact@viral32111.com"
	} )
	auditLogResponse.raise_for_status()
	auditLogResults = auditLogResponse.json()
	auditLogCache = { entry[ "id" ]: entry[ "options" ][ "count" ] for entry in auditLogResults[ "audit_log_entries" ] }
	consoleLog( "Cached the last 100 message deletion events from the primary server's Audit Log." )

	# Log a message to the console
	consoleLog( "Ready!" )

# Register pre-ready event handlers
bot.event( on_connect )
bot.event( on_disconnect )
bot.event( on_resume )
bot.event( on_ready )
consoleLog( "Registered pre-ready event handlers." )

try:
	consoleLog( "Connecting..." )
	bot.loop.run_until_complete( bot.start( os.environ[ "BOT_TOKEN" ] ) )
except KeyboardInterrupt:
	consoleLog( "Stopping..." )

	# Remove all event handlers
	del bot.on_connect
	del bot.on_disconnect
	del bot.on_resume
	del bot.on_ready
	del bot.on_message
	del bot.on_raw_message_delete
	del bot.on_raw_message_edit
	del bot.on_member_join
	del bot.on_member_remove
	del bot.on_guild_update
	del bot.on_guild_channel_create
	del bot.on_guild_channel_delete
	del bot.on_guild_channel_update
	del bot.on_guild_role_create
	del bot.on_guild_role_delete
	del bot.on_guild_role_update
	del bot.on_application_command
	del bot.on_message_component
	del bot.on_socket_response
	consoleLog( "Removed all event handlers." )

	# Cleanup the relay
	relay.cleanup()
	consoleLog( "Cleaned up the relay." )

	# Enable default join notifications on the server
	primaryServer = bot.get_guild( PRIMARY_SERVER_ID ) # Fetch again in-case we never got to the ready event
	systemChannelFlags = primaryServer.system_channel_flags
	systemChannelFlags.join_notifications = True
	bot.loop.run_until_complete( primaryServer.edit(
		system_channel_flags = systemChannelFlags,
		reason = "Enable default join messages."
	) )
	consoleLog( "Enabled default join messages for '{serverName}' ({serverID}).".format(
		serverName = emoji.demojize( primaryServer.name ),
		serverID = primaryServer.id
	) )

	bot.loop.run_until_complete( bot.change_presence( status = discord.Status.offline ) )
	consoleLog( "Cleared current activity and set status to offline." )

	consoleLog( "Closing log file '{logPath}'...".format(
		logPath = logFile.name
	) )
	logFile.close()

	bot.loop.run_until_complete( bot.close() )
finally:
	bot.loop.close()
