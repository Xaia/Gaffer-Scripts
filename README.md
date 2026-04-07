# Gaffer-Scripts
Bunch of small scripts for Gaffer


Variables editor guide

The key node: NameSwitch
Gaffer's NameSwitch node is the bridge between your context variables and the node graph. It reads a variable and routes the matching input through.
Step-by-step for your Cloudy / Sunny lights example:
1. Create the variable + presets
Variables > Edit Variables... > "+ Add Variable" > name it lightSetup
Click Presets... > add two presets:
Name: Cloudy Value: Cloudy
Name: Sunny Value: Sunny
Done. Now your Variables menu has lightSetup > Cloudy / Sunny
2. Add a NameSwitch node in the graph
In the node graph, create a NameSwitch node (Tab menu > search "NameSwitch")
Connect the Cloudy light branch output to NameSwitch in0
Connect the Sunny light branch output to NameSwitch in1
3. Label the NameSwitch inputs
In the NameSwitch's node editor, set the name for each input:
in0 name = Cloudy
in1 name = Sunny
4. Set the selector to read your variable
In the NameSwitch, set the selector field to:
${lightSetup}
The ${} syntax reads the context variable by name.
5. Connect the NameSwitch output to your LIGHTS group (replacing the direct connections)
The result:
  Cloudy branch ──┐
                   ├── NameSwitch (selector: ${lightSetup}) ──► LIGHTS ──► rest of graph
  Sunny branch  ──┘
Now when you go Variables > lightSetup > Sunny, the NameSwitch instantly routes the Sunny branch through. Pick Cloudy and it switches. One click, real-time, undoable.
Other useful patterns
What you want	Node to use	Selector
Switch between whole branches (lights, cameras, geo)	NameSwitch	${variableName}
Drive a single parameter from a variable (e.g. resolution)	Spreadsheet	Row selector = ${variableName}
Toggle a node on/off based on a variable	Expression on the enabled plug	parent["enabled"] = context["myFlag"] == "on"
Switch between 2 things by index	Switch with expression	parent["index"] = 1 if context["quality"] == "high" else 0
The NameSwitch is by far the most artist-friendly -- it matches strings directly, so your preset values just need to match the input names. No code, no expressions, just names.
