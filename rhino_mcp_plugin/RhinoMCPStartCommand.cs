using System;
using System.Collections.Generic;
using Rhino;
using Rhino.Commands;
using Rhino.Geometry;
using Rhino.Input;
using Rhino.Input.Custom;
using ModelContextProtocol;
using ModelContextProtocol.Server;
using Microsoft.Extensions.Hosting;
using System.ComponentModel;
using System.Threading.Tasks;

namespace RhinoMCPPlugin
{
    public class RhinoMCPStartCommand : Command
    {
        public RhinoMCPStartCommand()
        {
            // Rhino only creates one instance of each command class defined in a
            // plug-in, so it is safe to store a refence in a static property.
            Instance = this;
        }

        ///<summary>The only instance of this command.</summary>
        public static RhinoMCPStartCommand Instance { get; private set; }

        

        public override string EnglishName => "RhinoMCPStart";

        protected override Result RunCommand(RhinoDoc doc, RunMode mode)
        {
            RhinoMCPServerController.StartServer();
            return Result.Success;
        }

    }
}
