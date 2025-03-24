using System;
using System.Drawing;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using rhinomcp.Serializers;
using Rhino.Runtime;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject ExecuteRhinoscript(JObject parameters)
        {
            var doc = RhinoDoc.ActiveDoc;
            string code = parameters["code"]?.ToString();
            if (string.IsNullOrEmpty(code))
            {
                throw new Exception("Code is required");
            }

            try
            {
                // Create a new Python script instance
                PythonScript pythonScript = PythonScript.Create();
                
                // Setup the script context with the current document
                if (doc != null)
                    pythonScript.SetupScriptContext(doc);

                // Execute the Python code
                pythonScript.ExecuteScript(code);
                
                return new JObject
                {
                    ["result"] = "Script successfully executed"
                };
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException("Failed to execute rhinoscript");
            }
        }
}