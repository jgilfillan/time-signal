import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1])
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[1])
print("filled")
ok = pcbnew.WriteDRCReport(b, sys.argv[2], pcbnew.EDA_UNITS_MILLIMETRES, True)
print("drc", ok)
