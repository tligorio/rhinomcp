using System;
using System.Linq;
using Newtonsoft.Json.Linq;
using Rhino;
using Rhino.DocObjects;
using rhinomcp.Serializers;

namespace RhinoMCPPlugin.Functions;

public partial class RhinoMCPFunctions
{
    private RhinoObject getObjectByIdOrName(JObject parameters)
    {
        string objectId = parameters["id"]?.ToString();
        string objectName = parameters["name"]?.ToString();

        var doc = RhinoDoc.ActiveDoc;
        RhinoObject obj = null;

        if (!string.IsNullOrEmpty(objectId))
            obj = doc.Objects.Find(new Guid(objectId));
        else if (!string.IsNullOrEmpty(objectName))
        {
            // we assume there's only one of the object with the given name
            var objs = doc.Objects.GetObjectList(new ObjectEnumeratorSettings() { NameFilter = objectName }).ToList();
            if (objs == null) throw new InvalidOperationException($"Object with name {objectName} not found.");
            if (objs.Count > 1) throw new InvalidOperationException($"Multiple objects with name {objectName} found.");
            obj = objs[0];
        }

        if (obj == null)
            throw new InvalidOperationException($"Object with ID {objectId} not found");
        return obj;
    }
}