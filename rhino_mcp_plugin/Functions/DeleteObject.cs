using System;
using Newtonsoft.Json.Linq;
using Rhino;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject DeleteObject(JObject parameters)
    {
        var obj = getObjectByIdOrName(parameters);

        var doc = RhinoDoc.ActiveDoc;
        bool success = doc.Objects.Delete(obj.Id, true);

        if (!success)
            throw new InvalidOperationException($"Failed to delete object with ID {obj.Id}");

        // Update views
        doc.Views.Redraw();

        return new JObject
        {
            ["id"] = obj.Id,
            ["name"] = obj.Name,
            ["deleted"] = true
        };
    }
}