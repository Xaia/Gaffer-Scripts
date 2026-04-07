##########################################################################
#
#  Variables Editor — Katana-style Context Variables Manager for Gaffer
#
#  Startup script: place in  ~/gaffer/startup/gui/variablesEditor.py
#  Tested on Gaffer 1.6.15.0 (Windows)
#
#  Menu bar gets a "Variables" dropdown with:
#    - Live per-variable submenus (click a preset to switch instantly)
#    - "Edit Variables…" to open the management panel
#
##########################################################################

import functools

import imath
import IECore
import Gaffer
import GafferUI


# =========================================================================
#   Quick-switch helpers  (used by the menu)
# =========================================================================

def _setPresetValue( plug, value, checkBox ) :
	with Gaffer.UndoScope( plug.ancestor( Gaffer.ScriptNode ) ) :
		plug.setValue( value )


def _getVarInfo( member ) :
	varName   = member["name"].getValue() if "name" in member else member.getName()
	valuePlug = member["value"] if "value" in member else member
	try :
		currentVal = str( valuePlug.getValue() )
	except Exception :
		currentVal = ""
	presetNames  = Gaffer.Metadata.value( valuePlug, "presetNames" )  or IECore.StringVectorData()
	presetValues = Gaffer.Metadata.value( valuePlug, "presetValues" ) or IECore.StringVectorData()
	return varName, valuePlug, currentVal, list( presetNames ), list( presetValues )


# =========================================================================
#   Dynamic "Variables" menu  (rebuilt every time it opens)
# =========================================================================

def __variablesMenu( menu ) :

	script  = menu.ancestor( GafferUI.ScriptWindow ).scriptNode()
	members = list( script["variables"].children() )
	result  = IECore.MenuDefinition()

	for member in members :
		varName, valuePlug, currentVal, pNames, pValues = _getVarInfo( member )

		if pNames :
			for i in range( len( pNames ) ) :
				result.append(
					"/{}/{}".format( varName, pNames[i] ),
					{
						"command"  : functools.partial( _setPresetValue, valuePlug, pValues[i] ),
						"checkBox" : ( currentVal == pValues[i] ),
					},
				)
		else :
			result.append(
				"/{}".format( varName ),
				{
					"command" : functools.partial( _showEditorForVar, script, varName ),
					"description" : "Current value: {}  (no presets — click to open editor)".format( currentVal ),
				},
			)

	if members :
		result.append( "/divider", { "divider" : True } )

	result.append(
		"/Edit Variables\u2026",
		{ "command" : functools.partial( _showEditor, script ) },
	)

	return result


# =========================================================================
#   Show / reuse editor window
# =========================================================================

_editors = {}

def _showEditor( script ) :
	key = id( script )
	editor = _editors.get( key )
	if editor is not None :
		editor._refresh()
		editor.setVisible( True )
		return
	editor = _VariablesEditor( script )
	_editors[key] = editor
	editor.setVisible( True )

def _showEditorForVar( script, varName ) :
	_showEditor( script )


# =========================================================================
#   Main editor window
# =========================================================================

class _VariablesEditor( GafferUI.Window ) :

	def __init__( self, scriptNode ) :

		GafferUI.Window.__init__( self, "Context Variables Editor", borderWidth=8 )
		self._qtWidget().resize( 950, 650 )

		self.__script = scriptNode
		self.__vars   = scriptNode["variables"]

		column = GafferUI.ListContainer(
			GafferUI.ListContainer.Orientation.Vertical, spacing=8
		)
		self.setChild( column )

		with column :

			with GafferUI.ListContainer(
				GafferUI.ListContainer.Orientation.Horizontal, spacing=8
			) :
				GafferUI.Label( "<h3>Context Variables</h3>" )
				GafferUI.Spacer( imath.V2i( 1, 1 ), parenting={ "expand" : True } )
				self.__addBtn     = GafferUI.Button( "+  Add Variable" )
				self.__refreshBtn = GafferUI.Button( "Refresh" )

			GafferUI.Divider()

			with GafferUI.ScrolledContainer(
				horizontalMode = GafferUI.ScrollMode.Never,
				verticalMode   = GafferUI.ScrollMode.Automatic,
				borderWidth    = 2,
				parenting      = { "expand" : True },
			) :
				self.__rows = GafferUI.ListContainer(
					GafferUI.ListContainer.Orientation.Vertical,
					spacing     = 6,
					borderWidth = 4,
				)

			GafferUI.Divider()

			with GafferUI.ListContainer(
				GafferUI.ListContainer.Orientation.Horizontal, spacing=8
			) :
				GafferUI.Spacer( imath.V2i( 1, 1 ), parenting={ "expand" : True } )
				self.__closeBtn = GafferUI.Button( "Close" )

		self.__addBtn.clickedSignal().connect(
			Gaffer.WeakMethod( self.__onAdd ), scoped=False
		)
		self.__refreshBtn.clickedSignal().connect(
			Gaffer.WeakMethod( self.__onRefresh ), scoped=False
		)
		self.__closeBtn.clickedSignal().connect(
			Gaffer.WeakMethod( self.__onClose ), scoped=False
		)

		self.__rebuild()

	def _refresh( self ) :
		self.__rebuild()

	# -- row building ------------------------------------------------------

	def __rebuild( self ) :

		del self.__rows[:]
		members = list( self.__vars.children() )

		if not members :
			with self.__rows :
				GafferUI.Label(
					"No variables defined yet.  Click  \"+  Add Variable\"  to create one.",
					horizontalAlignment = GafferUI.Label.HorizontalAlignment.Center,
				)
			return

		for member in members :
			self.__buildRow( member )

	def __buildRow( self, member ) :

		varName, valuePlug, currentVal, pNames, pValues = _getVarInfo( member )

		with self.__rows :
			with GafferUI.ListContainer(
				GafferUI.ListContainer.Orientation.Horizontal, spacing=8
			) as row :

				nameLabel = GafferUI.Label( "<b>{}</b>".format( varName ) )
				nameLabel._qtWidget().setFixedWidth( 200 )

				widget = GafferUI.PlugValueWidget.create( valuePlug )
				if widget is not None :
					row.setExpand( widget, True )
				else :
					GafferUI.Label( currentVal, parenting={ "expand" : True } )

				if pNames :
					infoLabel = GafferUI.Label(
						"({} presets)".format( len( pNames ) )
					)
				else :
					infoLabel = GafferUI.Label( "(no presets)" )

				presetsBtn = GafferUI.Button( "Presets\u2026" )
				presetsBtn.clickedSignal().connect(
					functools.partial( Gaffer.WeakMethod( self.__onPresets ), valuePlug ),
					scoped = False,
				)

				deleteBtn = GafferUI.Button( "Delete" )
				deleteBtn.clickedSignal().connect(
					functools.partial( Gaffer.WeakMethod( self.__onDelete ), member ),
					scoped = False,
				)

	# -- handlers ----------------------------------------------------------

	def __onAdd( self, button ) :

		dialogue = GafferUI.TextInputDialogue(
			initialText  = "myVariable",
			title        = "New Variable Name",
			confirmLabel = "Add",
		)
		name = dialogue.waitForText( parentWindow=self )
		if not name :
			return

		plugName = name.replace( ":", "_" ).replace( " ", "_" )

		with Gaffer.UndoScope( self.__script ) :
			self.__vars.addChild(
				Gaffer.NameValuePlug(
					name,
					IECore.StringData( "" ),
					True,
					plugName,
					Gaffer.Plug.Direction.In,
					Gaffer.Plug.Flags.Default | Gaffer.Plug.Flags.Dynamic,
				)
			)
		self.__rebuild()

	def __onDelete( self, member, button ) :

		with Gaffer.UndoScope( self.__script ) :
			self.__vars.removeChild( member )
		self.__rebuild()

	def __onPresets( self, valuePlug, button ) :

		dialogue = _PresetsDialogue( valuePlug )
		dialogue.waitForButton( parentWindow=self )
		self.__rebuild()

	def __onRefresh( self, button ) :
		self.__rebuild()

	def __onClose( self, button ) :
		self.close()


# =========================================================================
#   Presets dialogue  (modal)
# =========================================================================

class _PresetsDialogue( GafferUI.Dialogue ) :

	def __init__( self, valuePlug ) :

		varPath = valuePlug.relativeName( valuePlug.ancestor( Gaffer.ScriptNode ) )

		GafferUI.Dialogue.__init__(
			self,
			"Presets  \u2014  {}".format( varPath ),
			borderWidth = 8,
			sizeMode    = GafferUI.Window.SizeMode.Manual,
		)
		self._qtWidget().resize( 600, 450 )

		self.__plug = valuePlug

		column = GafferUI.ListContainer(
			GafferUI.ListContainer.Orientation.Vertical, spacing=8
		)
		self._setWidget( column )

		with column :

			GafferUI.Label( "<b>Existing Presets</b>" )

			with GafferUI.ScrolledContainer(
				horizontalMode = GafferUI.ScrollMode.Never,
				verticalMode   = GafferUI.ScrollMode.Automatic,
				parenting      = { "expand" : True },
			) :
				self.__presetRows = GafferUI.ListContainer(
					GafferUI.ListContainer.Orientation.Vertical,
					spacing     = 4,
					borderWidth = 2,
				)

			GafferUI.Divider()

			GafferUI.Label( "<b>Add New Preset</b>" )

			with GafferUI.ListContainer(
				GafferUI.ListContainer.Orientation.Horizontal, spacing=8
			) :
				GafferUI.Label( "Name:" )
				self.__nameField = GafferUI.TextWidget( placeholderText="e.g. Low Quality" )
				GafferUI.Label( "Value:" )
				self.__valueField = GafferUI.TextWidget( placeholderText="e.g. 128" )
				self.__addPresetBtn = GafferUI.Button( "+  Add" )

		self.__addPresetBtn.clickedSignal().connect(
			Gaffer.WeakMethod( self.__onAddPreset ), scoped=False
		)

		self._addButton( "Done" )
		self.__rebuildList()

	def __rebuildList( self ) :

		del self.__presetRows[:]

		names  = Gaffer.Metadata.value( self.__plug, "presetNames" )  or IECore.StringVectorData()
		values = Gaffer.Metadata.value( self.__plug, "presetValues" ) or IECore.StringVectorData()

		if not len( names ) :
			with self.__presetRows :
				GafferUI.Label(
					"No presets defined yet.",
					horizontalAlignment = GafferUI.Label.HorizontalAlignment.Center,
				)
			return

		for i in range( len( names ) ) :
			with self.__presetRows :
				with GafferUI.ListContainer(
					GafferUI.ListContainer.Orientation.Horizontal, spacing=8
				) :
					nameLabel = GafferUI.Label( "<b>{}</b>".format( names[i] ) )
					nameLabel._qtWidget().setFixedWidth( 160 )
					GafferUI.Label( "\u2192  {}".format( str( values[i] ) ) )
					GafferUI.Spacer( imath.V2i( 1, 1 ), parenting={ "expand" : True } )
					removeBtn = GafferUI.Button( "Remove" )
					removeBtn.clickedSignal().connect(
						functools.partial( Gaffer.WeakMethod( self.__onRemovePreset ), i ),
						scoped = False,
					)

	def __onAddPreset( self, button ) :

		name  = self.__nameField.getText().strip()
		value = self.__valueField.getText().strip()
		if not name :
			return

		names  = list( Gaffer.Metadata.value( self.__plug, "presetNames" )  or [] )
		values = list( Gaffer.Metadata.value( self.__plug, "presetValues" ) or [] )
		names.append( name )
		values.append( value )

		Gaffer.Metadata.registerValue( self.__plug, "presetNames",  IECore.StringVectorData( names ) )
		Gaffer.Metadata.registerValue( self.__plug, "presetValues", IECore.StringVectorData( values ) )
		Gaffer.Metadata.registerValue( self.__plug, "plugValueWidget:type", "GafferUI.PresetsPlugValueWidget" )

		self.__nameField.setText( "" )
		self.__valueField.setText( "" )
		self.__rebuildList()

	def __onRemovePreset( self, index, button ) :

		names  = list( Gaffer.Metadata.value( self.__plug, "presetNames" )  or [] )
		values = list( Gaffer.Metadata.value( self.__plug, "presetValues" ) or [] )

		if index < len( names ) :
			del names[index]
			del values[index]

		Gaffer.Metadata.registerValue( self.__plug, "presetNames",  IECore.StringVectorData( names ) )
		Gaffer.Metadata.registerValue( self.__plug, "presetValues", IECore.StringVectorData( values ) )

		if not names :
			Gaffer.Metadata.registerValue( self.__plug, "plugValueWidget:type", "" )

		self.__rebuildList()


# =========================================================================
#   Menu registration
# =========================================================================

GafferUI.ScriptWindow.menuDefinition( application ).append(
	"/Variables", { "subMenu" : __variablesMenu }
)
