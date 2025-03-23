using Newtonsoft.Json.Linq;
using Rhino;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject GetSelectedObjectsInfo(JObject parameters)
    {
        var doc = RhinoDoc.ActiveDoc;
        var selectedObjs = doc.Objects.GetSelectedObjects(false, false);

        var result = new JArray();
        foreach (var obj in selectedObjs) result.Add(Serializer.RhinoObject(obj));
            
        return new JObject
        {
            ["selected_objects"] = result
        };
    }
}