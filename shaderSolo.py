##########################################################################
#
#  Shader Solo — Preview any shader node's output in isolation
#
#  Right-click a shader node in the Graph Editor:
#    "Solo This Shader"  — routes its output through a flat/constant
#                          shader so you see only that texture/pattern
#    "Unsolo"            — restores the original shader connection
#
#  Supports: Arnold (ai:*), Cycles (cycles:*), OSL via Arnold (osl:*)
#  Fully undoable via Ctrl+Z as a fallback.
#
##########################################################################

import functools

import IECore
import Gaffer
import GafferUI
import GafferScene

# =========================================================================
#   Solo state  (single global — one solo active at a time)
# =========================================================================

_soloState = None


def _isSoloing() :

	global _soloState

	if _soloState is None :
		return False

	try :
		flatNode = _soloState["flatNode"]
		if flatNode.parent() is None :
			_soloState = None
			return False
	except Exception :
		_soloState = None
		return False

	return True


# =========================================================================
#   Network traversal
# =========================================================================

def _findAssignment( shaderNode ) :
	"""Walk downstream outputs from a shader to find the ShaderAssignment."""

	visited = set()

	def _walk( plug ) :
		pid = id( plug )
		if pid in visited :
			return None
		visited.add( pid )

		for dest in plug.outputs() :
			node = dest.node()
			if isinstance( node, GafferScene.ShaderAssignment ) :
				return node
			if isinstance( node, GafferScene.Shader ) and "out" in node :
				result = _walk( node["out"] )
				if result is not None :
					return result
			else :
				result = _walk( dest )
				if result is not None :
					return result

		for child in plug.children() :
			result = _walk( child )
			if result is not None :
				return result

		return None

	if "out" not in shaderNode :
		return None
	return _walk( shaderNode["out"] )


def _rendererPrefix( shaderNode ) :

	shaderType = shaderNode["type"].getValue()
	return shaderType.split( ":" )[0] if ":" in shaderType else ""


# =========================================================================
#   Diagnostic shader creation  (per renderer)
# =========================================================================

def _createFlatShader( prefix, parent ) :
	"""Create a flat/constant diagnostic shader.

	Returns ( node, colorInputPlug, outputPlug ) or ( None, None, None ).
	The node is added to `parent` as a child.
	"""

	if prefix in ( "ai", "osl" ) :
		try :
			import GafferArnold
			node = GafferArnold.ArnoldShader( "__SoloPreview" )
			parent.addChild( node )
			node.loadShader( "flat" )
			return node, node["parameters"]["color"], node["out"]
		except Exception :
			return None, None, None

	if prefix == "cycles" :
		try :
			import GafferCycles
			node = GafferCycles.CyclesShader( "__SoloPreview" )
			parent.addChild( node )
			node.loadShader( "emission" )
			return node, node["parameters"]["color"], node["out"]
		except Exception :
			return None, None, None

	return None, None, None


# =========================================================================
#   Connection helpers
# =========================================================================

def _tryConnect( sourcePlug, destPlug ) :
	"""Connect sourcePlug -> destPlug, trying various strategies."""

	try :
		destPlug.setInput( sourcePlug )
		return True
	except Exception :
		pass

	for name in ( "color", "rgb", "out_color", "outColor", "Color", "RGB", "c" ) :
		if name in sourcePlug :
			try :
				destPlug.setInput( sourcePlug[name] )
				return True
			except Exception :
				pass

	if len( destPlug ) >= 3 :
		try :
			for child in list( destPlug.children() )[:3] :
				child.setInput( sourcePlug )
			return True
		except Exception :
			pass

	for child in sourcePlug.children() :
		try :
			destPlug.setInput( child )
			return True
		except Exception :
			pass

	return False


# =========================================================================
#   Solo / Unsolo
# =========================================================================

def _solo( shaderNode, outputPlug=None ) :

	global _soloState

	scriptNode = shaderNode.ancestor( Gaffer.ScriptNode )
	if scriptNode is None :
		IECore.msg( IECore.Msg.Level.Error, "Shader Solo", "Cannot find ScriptNode." )
		return

	# Always clean up any existing solo first so the graph is in its
	# original state before we search for the assignment.
	_unsolo()

	assignment = _findAssignment( shaderNode )
	if assignment is None :
		IECore.msg(
			IECore.Msg.Level.Warning, "Shader Solo",
			"Cannot find a ShaderAssignment downstream of '{}'.".format( shaderNode.getName() ),
		)
		return

	prefix = _rendererPrefix( shaderNode )
	if not prefix :
		IECore.msg(
			IECore.Msg.Level.Warning, "Shader Solo",
			"Cannot determine renderer for '{}' (type='{}').".format(
				shaderNode.getName(), shaderNode["type"].getValue()
			),
		)
		return

	originalInput = assignment["shader"].getInput()
	if originalInput is None :
		IECore.msg(
			IECore.Msg.Level.Warning, "Shader Solo",
			"ShaderAssignment '{}' has no shader connected.".format( assignment.getName() ),
		)
		return

	shaderParent = shaderNode.parent()

	with Gaffer.UndoScope( scriptNode ) :

		flatNode, colorPlug, flatOut = _createFlatShader( prefix, shaderParent )
		if flatNode is None :
			IECore.msg(
				IECore.Msg.Level.Error, "Shader Solo",
				"Cannot create diagnostic shader for renderer '{}'.".format( prefix ),
			)
			return

		soloOutput = outputPlug if outputPlug is not None else shaderNode["out"]

		if not _tryConnect( soloOutput, colorPlug ) :
			shaderParent.removeChild( flatNode )
			IECore.msg(
				IECore.Msg.Level.Error, "Shader Solo",
				"Cannot connect '{}' to diagnostic shader.".format( soloOutput.fullName() ),
			)
			return

		assignment["shader"].setInput( flatOut )

	_soloState = {
		"flatNode"      : flatNode,
		"originalInput" : originalInput,
		"assignment"    : assignment,
		"scriptNode"    : scriptNode,
		"soloNodeName"  : shaderNode.getName(),
	}

	IECore.msg(
		IECore.Msg.Level.Info, "Shader Solo",
		"Soloing '{}' -> '{}' (right-click > Unsolo to restore)".format(
			shaderNode.getName(), assignment.getName()
		),
	)


def _unsolo( *unused ) :

	global _soloState

	if _soloState is None :
		return

	state = _soloState
	_soloState = None

	scriptNode = state.get( "scriptNode" )

	try :
		with Gaffer.UndoScope( scriptNode ) :
			state["assignment"]["shader"].setInput( state["originalInput"] )

			flatNode = state["flatNode"]
			if flatNode.parent() is not None :
				flatNode.parent().removeChild( flatNode )
	except Exception as e :
		IECore.msg(
			IECore.Msg.Level.Warning, "Shader Solo",
			"Error during unsolo: {}".format( e ),
		)
		return

	IECore.msg( IECore.Msg.Level.Info, "Shader Solo", "Restored original shader." )


# =========================================================================
#   Context menu integration
# =========================================================================

def __nodeContextMenu( graphEditor, node, menuDefinition ) :

	if not isinstance( node, GafferScene.Shader ) :
		return

	menuDefinition.append( "/__soloDiv", { "divider" : True } )

	if _isSoloing() :
		menuDefinition.append(
			"/Unsolo  ({})".format( _soloState["soloNodeName"] ),
			{ "command" : _unsolo },
		)

	canSolo = _findAssignment( node ) is not None
	menuDefinition.append(
		"/Solo This Shader",
		{
			"command" : functools.partial( _solo, node ),
			"active"  : canSolo,
		},
	)


def __plugContextMenu( graphEditor, plug, menuDefinition ) :

	node = plug.node()
	if not isinstance( node, GafferScene.Shader ) :
		return

	if "out" not in node :
		return
	if not ( node["out"].isAncestorOf( plug ) or plug is node["out"] ) :
		return

	menuDefinition.append( "/__soloDiv", { "divider" : True } )

	if _isSoloing() :
		menuDefinition.append(
			"/Unsolo  ({})".format( _soloState["soloNodeName"] ),
			{ "command" : _unsolo },
		)

	canSolo = _findAssignment( node ) is not None
	menuDefinition.append(
		"/Solo This Output",
		{
			"command" : functools.partial( _solo, node, plug ),
			"active"  : canSolo,
		},
	)


GafferUI.GraphEditor.nodeContextMenuSignal().connect( __nodeContextMenu )
GafferUI.GraphEditor.plugContextMenuSignal().connect( __plugContextMenu )
