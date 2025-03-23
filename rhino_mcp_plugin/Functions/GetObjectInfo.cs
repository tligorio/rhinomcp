using System;
using Newtonsoft.Json.Linq;
using Rhino;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    public JObject GetObjectInfo(JObject parameters)
    {
        var obj = getObjectByIdOrName(parameters);

        return Serializer.RhinoObject(obj);
    }
}